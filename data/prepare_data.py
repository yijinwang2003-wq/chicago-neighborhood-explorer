#!/usr/bin/env python3
"""Download and prepare CSV files for the final MySQL schema.

The script writes raw source extracts under data/raw and MySQL-ready CSV files
under data/processed. It intentionally produces base-table data only; aggregate
tables such as neighborhood profiles are SQL views.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import logging
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point


CHICAGO_RESOURCE = "https://data.cityofchicago.org/resource/{dataset_id}.csv"
COMMUNITY_GEOJSON_URL = "https://data.cityofchicago.org/resource/igwz-8jzy.geojson"
WARD_GEOJSON_URL = "https://data.cityofchicago.org/resource/p293-wvbd.geojson"
CMAP_2025_ITEM_URL = (
    "https://www.arcgis.com/sharing/rest/content/items/"
    "945968efae634b3bb2def17185ad8dee?f=json"
)

DATASETS = {
    "housing": "s6ha-ppgi",
    "cta_stops": "8pix-ypme",
    "rail_monthly": "t2rn-p8d7",
    "crime": "ijzp-q8t2",
    "service_requests": "v6vf-nfxy",
}

LINE_DEFS = [
    (1, "Red", ("red",)),
    (2, "Blue", ("blue",)),
    (3, "Brown", ("brn", "brown")),
    (4, "Green", ("g", "green")),
    (5, "Orange", ("o", "org", "orange")),
    (6, "Purple", ("p", "pexp", "purple")),
    (7, "Pink", ("pnk", "pink")),
    (8, "Yellow", ("y", "yellow")),
]

SLIVER_SQ_MILES = 0.000001
SQ_FT_PER_SQ_MI = 27_878_400


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--start-date", default="2025-01-01")
    parser.add_argument("--end-date", default="2026-01-01")
    parser.add_argument("--page-size", type=int, default=50000)
    parser.add_argument("--service-page-size", type=int, default=10000)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument(
        "--cmap-csv",
        type=Path,
        help="Optional local CMAP Community Data Snapshots CSV. Use this if the ArcGIS item changes.",
    )
    parser.add_argument(
        "--allow-census-placeholder",
        action="store_true",
        help="Write zero/NULL census rows if CMAP download/column matching fails.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def norm_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    seen: dict[str, int] = {}
    columns: list[str] = []
    for column in df.columns:
        name = norm_name(column)
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        columns.append(name)
    df.columns = columns
    return df


def first_existing(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    for candidate in candidates:
        name = norm_name(candidate)
        if name in df.columns:
            return name
    return None


def find_column(df: pd.DataFrame, token_groups: Iterable[Iterable[str]]) -> str | None:
    for tokens in token_groups:
        wanted = [norm_name(token) for token in tokens]
        for column in df.columns:
            if all(token in column for token in wanted):
                return column
    return None


def clean_text(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )


def to_bool(value: object) -> int | None:
    if pd.isna(value):
        return None
    text = str(value).strip().lower()
    if text in {"true", "t", "yes", "y", "1"}:
        return 1
    if text in {"false", "f", "no", "n", "0"}:
        return 0
    return None


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, na_rep="")
    logging.info("wrote %s (%s rows)", path, len(df))


def month_windows(start_date: str, end_date: str) -> list[tuple[str, str]]:
    start = datetime.strptime(start_date, "%Y-%m-%d").date().replace(day=1)
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    windows = []
    current = start
    while current < end:
        if current.month == 12:
            next_month = current.replace(year=current.year + 1, month=1)
        else:
            next_month = current.replace(month=current.month + 1)
        windows.append((current.isoformat(), min(next_month, end).isoformat()))
        current = next_month
    return windows


def request_with_retry(url: str, *, params: dict | None = None, timeout: int = 180) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as exc:  # pragma: no cover - network-dependent retry path
            last_error = exc
            logging.warning("request failed on attempt %s: %s", attempt, exc)
    raise RuntimeError(f"request failed after retries: {url}") from last_error


def download_file(url: str, path: Path, *, skip_download: bool) -> None:
    if skip_download and path.exists():
        logging.info("using existing raw file %s", path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.info("downloading %s", url)
    response = request_with_retry(url, timeout=240)
    path.write_bytes(response.content)
    logging.info("saved %s", path)


def fetch_socrata_csv(
    dataset_id: str,
    path: Path,
    *,
    skip_download: bool,
    page_size: int,
    select: str | None = None,
    where: str | None = None,
    order: str | None = None,
) -> None:
    if skip_download and path.exists():
        logging.info("using existing raw file %s", path)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    url = CHICAGO_RESOURCE.format(dataset_id=dataset_id)
    offset = 0
    wrote_header = False
    total = 0

    while True:
        params = {"$limit": str(page_size), "$offset": str(offset)}
        if select:
            params["$select"] = select
        if where:
            params["$where"] = where
        if order:
            params["$order"] = order

        logging.info("downloading %s rows %s-%s", dataset_id, offset, offset + page_size - 1)
        response = request_with_retry(url, params=params)
        try:
            chunk = pd.read_csv(io.StringIO(response.text), dtype=str)
        except pd.errors.EmptyDataError:
            break
        if chunk.empty:
            break

        chunk.to_csv(path, mode="a", index=False, header=not wrote_header)
        wrote_header = True
        total += len(chunk)
        if len(chunk) < page_size:
            break
        offset += page_size

    logging.info("saved %s (%s raw rows)", path, total)


def download_cmap_csv(raw_dir: Path, *, cmap_csv: Path | None, skip_download: bool) -> Path:
    target = raw_dir / "cmap_community_data_snapshots_2025.csv"
    if cmap_csv:
        if not target.exists() or not skip_download:
            shutil.copyfile(cmap_csv, target)
        return target
    if skip_download and target.exists():
        return target

    logging.info("discovering CMAP 2025 ArcGIS service")
    item = request_with_retry(CMAP_2025_ITEM_URL).json()
    service_url = item.get("url")
    if not service_url:
        data_url = CMAP_2025_ITEM_URL.replace("?f=json", "/data?f=json")
        item_data = request_with_retry(data_url).json()
        service_url = item_data.get("url")
    if not service_url:
        raise RuntimeError(
            "Could not discover a CMAP 2025 feature service. Pass --cmap-csv with a local CSV."
        )

    rows: list[dict] = []
    layer = f"{service_url.rstrip('/')}/0/query"
    offset = 0
    while True:
        params = {
            "f": "json",
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "false",
            "resultOffset": str(offset),
            "resultRecordCount": "2000",
        }
        payload = request_with_retry(layer, params=params).json()
        features = payload.get("features", [])
        if not features:
            break
        rows.extend(feature.get("attributes", {}) for feature in features)
        if len(features) < 2000:
            break
        offset += 2000

    if not rows:
        raise RuntimeError("CMAP ArcGIS query returned no rows. Pass --cmap-csv with a local CSV.")
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(target, index=False)
    logging.info("saved %s (%s raw rows)", target, len(rows))
    return target


def load_community_gdf(raw_dir: Path, processed_dir: Path, skip_download: bool) -> gpd.GeoDataFrame:
    raw_path = raw_dir / "community_areas.geojson"
    download_file(COMMUNITY_GEOJSON_URL, raw_path, skip_download=skip_download)
    gdf = gpd.read_file(raw_path)
    gdf.columns = [norm_name(column) for column in gdf.columns]

    community_col = first_existing(gdf, ("area_num_1", "area_numbe", "community_id", "area_num"))
    name_col = first_existing(gdf, ("community", "name", "community_area_name", "area_name"))
    if not community_col or not name_col:
        raise RuntimeError("Community boundary file is missing community id or name fields.")

    gdf = gdf[[community_col, name_col, "geometry"]].rename(
        columns={community_col: "community_id", name_col: "name"}
    )
    gdf["community_id"] = to_number(gdf["community_id"]).astype("Int64")
    gdf = gdf[gdf["community_id"].between(1, 77)].copy()

    projected = gdf.to_crs("EPSG:3435")
    centroids = projected.geometry.centroid.to_crs("EPSG:4326")
    gdf["centroid_lat"] = centroids.y.round(7)
    gdf["centroid_lng"] = centroids.x.round(7)
    gdf["area_sq_miles"] = (projected.geometry.area / SQ_FT_PER_SQ_MI).round(6)
    gdf = gdf.sort_values("community_id")

    output = gdf[["community_id", "name", "centroid_lat", "centroid_lng", "area_sq_miles"]]
    write_csv(output, processed_dir / "community_areas.csv")
    if len(output) != 77:
        raise RuntimeError(f"Expected 77 community areas, found {len(output)}")
    return gdf.to_crs("EPSG:3435")


def prepare_wards_and_overlap(
    raw_dir: Path,
    processed_dir: Path,
    community_gdf_3435: gpd.GeoDataFrame,
    skip_download: bool,
) -> None:
    raw_path = raw_dir / "wards_2023.geojson"
    download_file(WARD_GEOJSON_URL, raw_path, skip_download=skip_download)
    wards = gpd.read_file(raw_path)
    wards.columns = [norm_name(column) for column in wards.columns]
    ward_col = first_existing(wards, ("ward", "ward_id"))
    if not ward_col:
        raise RuntimeError("Ward boundary file is missing ward id field.")

    wards = wards[[ward_col, "geometry"]].rename(columns={ward_col: "ward_id"})
    wards["ward_id"] = to_number(wards["ward_id"]).astype("Int64")
    wards = wards[wards["ward_id"].between(1, 50)].copy().to_crs("EPSG:3435")
    wards["ward_area_sq_ft"] = wards.geometry.area
    community = community_gdf_3435[["community_id", "geometry"]].copy()
    community["community_area_sq_ft"] = community.geometry.area

    write_csv(
        pd.DataFrame(
            {"ward_id": sorted(wards["ward_id"].dropna().astype(int)), "boundary_version": "2023-present"}
        ),
        processed_dir / "wards.csv",
    )

    bridge = gpd.overlay(community, wards, how="intersection")
    bridge["overlap_sq_ft"] = bridge.geometry.area
    bridge = bridge[bridge["overlap_sq_ft"] > SLIVER_SQ_MILES * SQ_FT_PER_SQ_MI].copy()
    bridge["overlap_sq_miles"] = (bridge["overlap_sq_ft"] / SQ_FT_PER_SQ_MI).round(6)
    bridge["pct_of_community_area"] = (
        bridge["overlap_sq_ft"] / bridge["community_area_sq_ft"] * 100
    ).round(3)
    bridge["pct_of_ward"] = (bridge["overlap_sq_ft"] / bridge["ward_area_sq_ft"] * 100).round(3)
    bridge = bridge[
        (bridge["overlap_sq_miles"] > 0)
        & (bridge["pct_of_community_area"] > 0)
        & (bridge["pct_of_ward"] > 0)
    ].copy()
    bridge = bridge.sort_values(["community_id", "ward_id"])
    output = bridge[
        ["community_id", "ward_id", "overlap_sq_miles", "pct_of_community_area", "pct_of_ward"]
    ]
    write_csv(output, processed_dir / "community_area_ward_overlap.csv")

    if not (output.groupby("community_id")["ward_id"].nunique() > 1).any():
        raise RuntimeError("Overlap output does not prove CommunityArea -> multiple Wards.")
    if not (output.groupby("ward_id")["community_id"].nunique() > 1).any():
        raise RuntimeError("Overlap output does not prove Ward -> multiple CommunityAreas.")


def community_lookup(community_gdf_3435: gpd.GeoDataFrame):
    areas = [
        (int(row.community_id), row.geometry)
        for row in community_gdf_3435[["community_id", "geometry"]].itertuples()
    ]

    def lookup(lat: object, lon: object) -> int | None:
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            return None
        if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
            return None
        point = gpd.GeoSeries([Point(lon_f, lat_f)], crs="EPSG:4326").to_crs("EPSG:3435").iloc[0]
        for community_id, polygon in areas:
            if polygon.covers(point):
                return community_id
        return None

    return lookup


def prepare_census_profiles(
    raw_dir: Path,
    processed_dir: Path,
    community_ids: set[int],
    *,
    cmap_csv: Path | None,
    skip_download: bool,
    allow_placeholder: bool,
) -> None:
    try:
        raw_path = download_cmap_csv(raw_dir, cmap_csv=cmap_csv, skip_download=skip_download)
        df = normalize_columns(pd.read_csv(raw_path, dtype=str))
        community_col = first_existing(df, ("geoid", "community_id", "cca", "area_num", "area_numbe"))
        if not community_col:
            raise RuntimeError("Could not find a community id/GEOID column in CMAP CSV.")

        population_col = first_existing(df, ("population", "total_population", "tot_pop"))
        if not population_col:
            population_col = find_column(df, (("total", "population"), ("population",)))
        income_col = first_existing(
            df,
            (
                "median_household_income",
                "median_hh_income",
                "med_hh_inc",
                "median_income",
                "medinc",
            ),
        ) or find_column(df, (("median", "household", "income"), ("median", "income")))
        age_col = first_existing(df, ("median_age", "med_age")) or find_column(df, (("median", "age"),))
        unemployment_col = first_existing(df, ("unemployment_rate", "pct_unemployed")) or find_column(
            df, (("unemployment",), ("unemployed",))
        )
        bachelors_col = first_existing(df, ("pct_bachelors", "bachelors_or_higher")) or find_column(
            df, (("bachelor",), ("college", "degree"))
        )
        cost_burden_col = first_existing(
            df,
            (
                "housing_cost_burden_30plus_pct",
                "cost_burden_30plus_pct",
                "housing_costs_30_percent_or_more",
            ),
        ) or find_column(df, (("housing", "30"), ("cost", "burden"), ("income", "housing")))

        if not population_col:
            raise RuntimeError("Could not identify a population field in CMAP CSV.")

        out = pd.DataFrame()
        out["community_id"] = to_number(df[community_col]).astype("Int64")
        out = out[out["community_id"].isin(community_ids)].copy()
        out["cmap_release_year"] = 2025
        out["acs_estimate_period"] = "2019-2023"
        out["population"] = to_number(df.loc[out.index, population_col]).fillna(0).astype(int)
        out["median_household_income"] = (
            to_number(df.loc[out.index, income_col]) if income_col else pd.NA
        )
        out["median_age"] = to_number(df.loc[out.index, age_col]) if age_col else pd.NA
        if {"unemp", "in_lbfrc"}.issubset(df.columns):
            out["unemployment_rate"] = (
                to_number(df.loc[out.index, "unemp"]) / to_number(df.loc[out.index, "in_lbfrc"]) * 100
            )
        else:
            out["unemployment_rate"] = (
                to_number(df.loc[out.index, unemployment_col]) if unemployment_col else pd.NA
            )
        if {"bach", "grad_prof", "pop_25ov"}.issubset(df.columns):
            out["pct_bachelors"] = (
                (to_number(df.loc[out.index, "bach"]) + to_number(df.loc[out.index, "grad_prof"]))
                / to_number(df.loc[out.index, "pop_25ov"])
                * 100
            )
        else:
            out["pct_bachelors"] = (
                to_number(df.loc[out.index, bachelors_col]) if bachelors_col else pd.NA
            )
        burden_30_cols = [
            "hcund20k_30mpct",
            "hc20kto49k_30mpct",
            "hc50kto75k_30mpct",
            "hcov75k_30mpct",
        ]
        burden_denominator_cols = [
            "hcund20k_lt20pct",
            "hcund20k_20_29pct",
            "hcund20k_30mpct",
            "hc20kto49k_lt20pct",
            "hc20kto49k_20_29pct",
            "hc20kto49k_30mpct",
            "hc50kto75k_lt20pct",
            "hc50kto75k_20_29pct",
            "hc50kto75k_30mpct",
            "hcov75k_lt20pct",
            "hcov75k_20_29pct",
            "hcov75k_30mpct",
        ]
        if set(burden_30_cols).issubset(df.columns) and set(burden_denominator_cols).issubset(
            df.columns
        ):
            burden_30 = sum(to_number(df.loc[out.index, column]) for column in burden_30_cols)
            burden_total = sum(
                to_number(df.loc[out.index, column]) for column in burden_denominator_cols
            )
            out["housing_cost_burden_30plus_pct"] = burden_30 / burden_total * 100
        else:
            out["housing_cost_burden_30plus_pct"] = (
                to_number(df.loc[out.index, cost_burden_col]) if cost_burden_col else pd.NA
            )
        for pct_col in ("unemployment_rate", "pct_bachelors", "housing_cost_burden_30plus_pct"):
            out[pct_col] = out[pct_col].round(3)
        out = out.drop_duplicates("community_id").sort_values("community_id")
        if len(out) != 77:
            raise RuntimeError(f"Expected 77 CMAP community profile rows, found {len(out)}")
        write_csv(out, processed_dir / "census_profiles.csv")
    except Exception:
        if not allow_placeholder:
            raise
        logging.exception("CMAP processing failed; writing placeholder census rows")
        out = pd.DataFrame({"community_id": sorted(community_ids)})
        out["cmap_release_year"] = 2025
        out["acs_estimate_period"] = "2019-2023"
        out["population"] = 0
        out["median_household_income"] = pd.NA
        out["median_age"] = pd.NA
        out["unemployment_rate"] = pd.NA
        out["pct_bachelors"] = pd.NA
        out["housing_cost_burden_30plus_pct"] = pd.NA
        write_csv(out, processed_dir / "census_profiles.csv")


def parse_point_column(value: object) -> tuple[float | None, float | None]:
    if pd.isna(value):
        return None, None
    text = str(value)
    numbers = re.findall(r"-?\d+\.\d+", text)
    if len(numbers) < 2:
        return None, None
    first, second = map(float, numbers[:2])
    if abs(first) > 90 and abs(second) <= 90:
        return second, first
    return first, second


def ensure_housing_raw(raw_dir: Path, skip_download: bool, page_size: int) -> Path:
    path = raw_dir / "affordable_rental_housing_developments.csv"
    fetch_socrata_csv(DATASETS["housing"], path, skip_download=skip_download, page_size=page_size)
    return path


def prepare_housing(
    raw_dir: Path,
    processed_dir: Path,
    community_gdf_3435: gpd.GeoDataFrame,
    *,
    skip_download: bool,
    page_size: int,
) -> None:
    raw_path = ensure_housing_raw(raw_dir, skip_download, page_size)
    df = normalize_columns(pd.read_csv(raw_path, dtype=str))

    property_col = first_existing(df, ("property_name", "name", "development_name"))
    address_col = first_existing(df, ("address", "street_address", "property_address"))
    type_col = first_existing(df, ("property_type", "type"))
    units_col = first_existing(df, ("units", "unit_count", "reported_unit_count", "number_of_units"))
    phone_col = first_existing(df, ("phone_number", "phone", "contact_phone"))
    company_col = first_existing(df, ("management_company", "company", "manager"))
    community_col = first_existing(df, ("community_area_number", "community_area", "community_id"))
    lat_col = first_existing(df, ("latitude", "lat"))
    lon_col = first_existing(df, ("longitude", "lon", "lng"))
    location_col = first_existing(df, ("location", "the_geom"))

    if not property_col or not address_col:
        raise RuntimeError("Housing source is missing property name or address.")

    out = pd.DataFrame()
    out["property_name"] = df[property_col].map(clean_text)
    out["address"] = df[address_col].map(clean_text)
    out["raw_property_type"] = df[type_col].map(clean_text) if type_col else pd.NA
    out["reported_unit_count"] = to_number(df[units_col]).astype("Int64") if units_col else pd.NA
    out["contact_phone"] = df[phone_col].map(clean_text) if phone_col else pd.NA
    out["company_name"] = df[company_col].map(clean_text) if company_col else pd.NA

    if lat_col and lon_col:
        out["latitude"] = to_number(df[lat_col]).round(7)
        out["longitude"] = to_number(df[lon_col]).round(7)
    elif location_col:
        points = df[location_col].map(parse_point_column)
        out["latitude"] = [lat for lat, _ in points]
        out["longitude"] = [lon for _, lon in points]
    else:
        out["latitude"] = pd.NA
        out["longitude"] = pd.NA

    if community_col:
        out["community_id"] = to_number(df[community_col]).astype("Int64")
    else:
        lookup = community_lookup(community_gdf_3435)
        out["community_id"] = [lookup(lat, lon) for lat, lon in zip(out["latitude"], out["longitude"])]
    out = out[out["community_id"].between(1, 77)].copy()

    companies = sorted({name for name in out["company_name"].dropna().astype(str) if name.strip()})
    company_df = pd.DataFrame(
        {"company_id": range(1, len(companies) + 1), "company_name": companies}
    )
    company_map = dict(zip(company_df["company_name"], company_df["company_id"]))

    def fingerprint(row: pd.Series) -> str:
        pieces = [
            row.get("property_name") or "",
            row.get("address") or "",
            str(row.get("community_id") or ""),
            row.get("raw_property_type") or "",
        ]
        return hashlib.sha256("|".join(pieces).lower().encode("utf-8")).hexdigest()

    out["source_record_key"] = out.apply(fingerprint, axis=1)
    out = out.drop_duplicates("source_record_key").reset_index(drop=True)
    out["development_id"] = range(1, len(out) + 1)
    out["company_id"] = out["company_name"].map(company_map).astype("Int64")
    out = out[
        [
            "development_id",
            "source_record_key",
            "property_name",
            "address",
            "raw_property_type",
            "reported_unit_count",
            "contact_phone",
            "latitude",
            "longitude",
            "community_id",
            "company_id",
        ]
    ]

    write_csv(company_df, processed_dir / "management_companies.csv")
    write_csv(out, processed_dir / "housing_developments.csv")


def prepare_cta(
    raw_dir: Path,
    processed_dir: Path,
    community_gdf_3435: gpd.GeoDataFrame,
    *,
    skip_download: bool,
    page_size: int,
) -> None:
    raw_path = raw_dir / "cta_l_stops.csv"
    fetch_socrata_csv(DATASETS["cta_stops"], raw_path, skip_download=skip_download, page_size=page_size)
    df = normalize_columns(pd.read_csv(raw_path, dtype=str))

    station_col = first_existing(df, ("map_id", "station_id"))
    name_col = first_existing(df, ("station_name", "station_descriptive_name", "stop_name"))
    ada_col = first_existing(df, ("ada", "ada_accessible"))
    lat_col = first_existing(df, ("latitude", "lat"))
    lon_col = first_existing(df, ("longitude", "lon", "lng"))
    location_col = first_existing(df, ("location",))
    if not station_col or not name_col:
        raise RuntimeError("CTA stop source is missing station id or station name.")

    work = pd.DataFrame()
    work["station_id"] = to_number(df[station_col]).astype("Int64")
    work["station_name"] = df[name_col].map(clean_text)
    work["ada_accessible"] = df[ada_col].map(to_bool) if ada_col else pd.NA
    if lat_col and lon_col:
        work["latitude"] = to_number(df[lat_col]).round(7)
        work["longitude"] = to_number(df[lon_col]).round(7)
    elif location_col:
        points = df[location_col].map(parse_point_column)
        work["latitude"] = [lat for lat, _ in points]
        work["longitude"] = [lon for _, lon in points]
    else:
        raise RuntimeError("CTA stop source is missing coordinates.")

    for line_id, _, candidates in LINE_DEFS:
        matching = [column for column in candidates if column in df.columns]
        if matching:
            work[f"line_{line_id}"] = df[matching].apply(
                lambda row: int(any(to_bool(value) == 1 for value in row)), axis=1
            )
        else:
            work[f"line_{line_id}"] = 0

    grouped = work.groupby("station_id", as_index=False).agg(
        {
            "station_name": "first",
            "ada_accessible": "max",
            "latitude": "first",
            "longitude": "first",
            **{f"line_{line_id}": "max" for line_id, _, _ in LINE_DEFS},
        }
    )

    lookup = community_lookup(community_gdf_3435)
    grouped["community_id"] = [
        lookup(lat, lon) for lat, lon in zip(grouped["latitude"], grouped["longitude"])
    ]
    stations = grouped[
        ["station_id", "station_name", "ada_accessible", "latitude", "longitude", "community_id"]
    ].sort_values("station_id")

    lines = pd.DataFrame(
        {"line_id": [line_id for line_id, _, _ in LINE_DEFS], "line_name": [name for _, name, _ in LINE_DEFS]}
    )
    serves_rows = []
    for row in grouped.itertuples(index=False):
        station_id = int(row.station_id)
        for line_id, _, _ in LINE_DEFS:
            if int(getattr(row, f"line_{line_id}")) == 1:
                serves_rows.append({"station_id": station_id, "line_id": line_id})
    serves = pd.DataFrame(serves_rows).sort_values(["station_id", "line_id"])

    write_csv(stations, processed_dir / "cta_rail_stations.csv")
    write_csv(lines, processed_dir / "cta_lines.csv")
    write_csv(serves, processed_dir / "serves.csv")


def prepare_rail_ridership(
    raw_dir: Path,
    processed_dir: Path,
    *,
    start_date: str,
    end_date: str,
    skip_download: bool,
    page_size: int,
) -> None:
    raw_path = raw_dir / "cta_rail_ridership_monthly_2025.csv"
    where = f"month_beginning >= '{start_date}T00:00:00' AND month_beginning < '{end_date}T00:00:00'"
    select = (
        "station_id,month_beginning,avg_weekday_rides,avg_saturday_rides,"
        "avg_sunday_holiday_rides,monthtotal"
    )
    fetch_socrata_csv(
        DATASETS["rail_monthly"],
        raw_path,
        skip_download=skip_download,
        page_size=page_size,
        select=select,
        where=where,
        order="station_id,month_beginning",
    )
    df = normalize_columns(pd.read_csv(raw_path, dtype=str))
    total_col = first_existing(df, ("monthtotal", "month_total"))
    out = pd.DataFrame()
    out["station_id"] = to_number(df["station_id"]).astype("Int64")
    out["month_beginning"] = pd.to_datetime(df["month_beginning"], errors="coerce").dt.date
    out["avg_weekday_rides"] = to_number(df["avg_weekday_rides"])
    out["avg_saturday_rides"] = to_number(df["avg_saturday_rides"])
    out["avg_sunday_holiday_rides"] = to_number(df["avg_sunday_holiday_rides"])
    out["month_total"] = to_number(df[total_col]).astype("Int64") if total_col else pd.NA
    out = out.dropna(subset=["station_id", "month_beginning"]).drop_duplicates(
        ["station_id", "month_beginning"]
    )
    write_csv(out.sort_values(["station_id", "month_beginning"]), processed_dir / "rail_ridership_monthly.csv")


def prepare_crime(
    raw_dir: Path,
    processed_dir: Path,
    *,
    start_date: str,
    end_date: str,
    skip_download: bool,
    page_size: int,
) -> None:
    raw_path = raw_dir / "crimes_2025.csv"
    where = (
        f"date >= '{start_date}T00:00:00' AND date < '{end_date}T00:00:00' "
        "AND community_area IS NOT NULL"
    )
    select = (
        "id,case_number,date,primary_type,description,location_description,arrest,"
        "domestic,latitude,longitude,community_area,updated_on"
    )
    fetch_socrata_csv(
        DATASETS["crime"],
        raw_path,
        skip_download=skip_download,
        page_size=page_size,
        select=select,
        where=where,
        order="id",
    )
    df = normalize_columns(pd.read_csv(raw_path, dtype=str))
    df["crime_id"] = to_number(df["id"]).astype("Int64")
    if "updated_on" in df.columns:
        df["_updated_on"] = pd.to_datetime(df["updated_on"], errors="coerce")
        df = df.sort_values(["crime_id", "_updated_on"]).drop_duplicates("crime_id", keep="last")
    else:
        df = df.drop_duplicates("crime_id", keep="last")

    out = pd.DataFrame()
    out["crime_id"] = df["crime_id"]
    out["case_number"] = df["case_number"].map(clean_text)
    out["crime_date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    out["primary_type"] = df["primary_type"].map(clean_text)
    out["description"] = df["description"].map(clean_text)
    out["location_description"] = df["location_description"].map(clean_text)
    out["arrest"] = df["arrest"].map(to_bool)
    out["domestic"] = df["domestic"].map(to_bool)
    out["latitude"] = to_number(df["latitude"]).round(7)
    out["longitude"] = to_number(df["longitude"]).round(7)
    out["community_id"] = to_number(df["community_area"]).astype("Int64")
    out = out.dropna(subset=["crime_id", "crime_date", "community_id"])
    out = out[out["community_id"].between(1, 77)]
    write_csv(out.sort_values("crime_id"), processed_dir / "crime_records.csv")


def prepare_service_requests(
    raw_dir: Path,
    processed_dir: Path,
    *,
    start_date: str,
    end_date: str,
    skip_download: bool,
    page_size: int,
) -> None:
    select = (
        "sr_number,sr_type,created_date,closed_date,status,street_address,zip_code,"
        "community_area,duplicate"
    )
    output_path = processed_dir / "service_requests.csv"
    if output_path.exists():
        output_path.unlink()
    wrote_header = False

    def append_processed(raw_path: Path) -> None:
        nonlocal wrote_header
        try:
            chunks = pd.read_csv(raw_path, dtype=str, chunksize=50000)
        except pd.errors.EmptyDataError:
            return
        for chunk in chunks:
            df = normalize_columns(chunk)
            if "duplicate" in df.columns:
                duplicate = df["duplicate"].astype(str).str.lower().eq("true")
                df = df[~duplicate].copy()
            request_col = first_existing(df, ("sr_type", "request_type", "service_request_type"))
            if not request_col:
                raise RuntimeError("311 source is missing a request type column.")
            out = pd.DataFrame()
            out["source_sr_number"] = df["sr_number"].map(clean_text)
            out["request_type"] = df[request_col].map(clean_text)
            out["created_date"] = pd.to_datetime(df["created_date"], errors="coerce").dt.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            out["closed_date"] = pd.to_datetime(df["closed_date"], errors="coerce").dt.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            out.loc[out["closed_date"].eq("NaT"), "closed_date"] = pd.NA
            out["status"] = df["status"].map(clean_text)
            out["street_address"] = df["street_address"].map(clean_text)
            out["zip_code"] = df["zip_code"].map(clean_text)
            out["community_id"] = to_number(df["community_area"]).astype("Int64")
            out["record_source"] = "OPEN_DATA"
            out = out.dropna(
                subset=["source_sr_number", "request_type", "created_date", "community_id"]
            )
            out = out[out["community_id"].between(1, 77)]
            out.to_csv(output_path, mode="a", index=False, header=not wrote_header, na_rep="")
            wrote_header = True

    for window_start, window_end in month_windows(start_date, end_date):
        month_label = window_start[:7].replace("-", "_")
        raw_path = raw_dir / f"service_requests_{month_label}.csv"
        where = (
            f"created_date >= '{window_start}T00:00:00' "
            f"AND created_date < '{window_end}T00:00:00' "
            "AND community_area IS NOT NULL"
        )
        fetch_socrata_csv(
            DATASETS["service_requests"],
            raw_path,
            skip_download=skip_download,
            page_size=page_size,
            select=select,
            where=where,
            order="sr_number",
        )
        append_processed(raw_path)

    logging.info("wrote %s", output_path)


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.processed_dir.mkdir(parents=True, exist_ok=True)

    community_gdf_3435 = load_community_gdf(args.raw_dir, args.processed_dir, args.skip_download)
    community_ids = set(community_gdf_3435["community_id"].astype(int))
    prepare_wards_and_overlap(args.raw_dir, args.processed_dir, community_gdf_3435, args.skip_download)
    prepare_census_profiles(
        args.raw_dir,
        args.processed_dir,
        community_ids,
        cmap_csv=args.cmap_csv,
        skip_download=args.skip_download,
        allow_placeholder=args.allow_census_placeholder,
    )
    prepare_housing(args.raw_dir, args.processed_dir, community_gdf_3435, skip_download=args.skip_download, page_size=args.page_size)
    prepare_cta(args.raw_dir, args.processed_dir, community_gdf_3435, skip_download=args.skip_download, page_size=args.page_size)
    prepare_rail_ridership(
        args.raw_dir,
        args.processed_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        skip_download=args.skip_download,
        page_size=args.service_page_size,
    )
    prepare_crime(
        args.raw_dir,
        args.processed_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        skip_download=args.skip_download,
        page_size=args.page_size,
    )
    prepare_service_requests(
        args.raw_dir,
        args.processed_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        skip_download=args.skip_download,
        page_size=args.page_size,
    )
    logging.info("all processed CSV files are ready in %s", args.processed_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
