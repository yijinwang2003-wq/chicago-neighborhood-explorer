#!/usr/bin/env python3
"""Load the lightweight Railway demo database from processed CSV files.

This script is designed for Railway MySQL and does not require a local MySQL
instance or mysqldump. It creates the demo schema, loads the processed CSVs,
builds the neighborhood profile snapshot, and verifies the resulting data.
"""

from __future__ import annotations

import argparse
import csv
import calendar
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import mysql.connector


DATA_DIR = Path("db-data/chicago_neighborhood_data")
SCHEMA_SQL = Path("sql/06_create_demo_database.sql")


def connect_server() -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ["MYSQL_PORT"]),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
    )


def ensure_database(cursor, database: str) -> None:
    cursor.execute(
        f"""
        CREATE DATABASE IF NOT EXISTS `{database}`
        CHARACTER SET utf8mb4
        COLLATE utf8mb4_unicode_ci
        """
    )
    cursor.execute(f"USE `{database}`")


def split_sql_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(buffer).rstrip().rstrip(";"))
            buffer = []
    if buffer:
        statements.append("\n".join(buffer).rstrip().rstrip(";"))
    return [statement for statement in statements if statement.strip()]


def execute_sql_file(cursor, path: Path) -> None:
    for statement in split_sql_statements(path.read_text(encoding="utf-8")):
        cursor.execute(statement)


def drop_demo_objects(cursor) -> None:
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    for name in (
        "vw_ward_community_profile",
        "vw_neighborhood_profile",
        "vw_crime_aggregation",
    ):
        cursor.execute(f"DROP VIEW IF EXISTS `{name}`")
    for name in (
        "neighborhood_profile_snapshot",
        "service_requests",
        "crime_records",
        "crime_aggregations",
        "rail_ridership_monthly",
        "serves",
        "cta_rail_stations",
        "cta_lines",
        "housing_developments",
        "management_companies",
        "community_area_ward_overlap",
        "wards",
        "neighborhood_profiles",
        "census_profiles",
        "community_areas",
    ):
        cursor.execute(f"DROP TABLE IF EXISTS `{name}`")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def to_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(float(value))


def to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def to_bool(value: str | None) -> int:
    return 1 if str(value).strip().lower() in {"1", "true", "t", "yes", "y"} else 0


def month_beginning(year: int, month: int) -> date:
    return date(year, month, 1)


def count_month_days(year: int, month: int) -> dict[str, int]:
    weekday_count = saturday_count = sunday_count = 0
    days_in_month = calendar.monthrange(year, month)[1]
    for day in range(1, days_in_month + 1):
        current = date(year, month, day)
        if current.weekday() == 5:
            saturday_count += 1
        elif current.weekday() == 6:
            sunday_count += 1
        else:
            weekday_count += 1
    return {"W": weekday_count, "A": saturday_count, "U": sunday_count}


def insert_rows(cursor, table: str, columns: list[str], rows: Iterable[tuple[Any, ...]], batch_size: int = 1000) -> int:
    placeholders = ", ".join(["%s"] * len(columns))
    column_list = ", ".join(f"`{column}`" for column in columns)
    sql = f"INSERT INTO `{table}` ({column_list}) VALUES ({placeholders})"
    batch: list[tuple[Any, ...]] = []
    total = 0
    for row in rows:
        batch.append(row)
        if len(batch) >= batch_size:
            cursor.executemany(sql, batch)
            total += len(batch)
            batch.clear()
    if batch:
        cursor.executemany(sql, batch)
        total += len(batch)
    return total


def load_community_areas(rows: list[dict[str, str]]) -> list[tuple[Any, ...]]:
    for row in rows:
        yield (
            to_int(row["community_id"]),
            row["name"],
            to_float(row["centroid_lat"]),
            to_float(row["centroid_lng"]),
            to_float(row["area_sq_miles"]),
        )


def load_census_profiles(rows: list[dict[str, str]]) -> list[tuple[Any, ...]]:
    for row in rows:
        yield (
            to_int(row["community_id"]),
            to_int(row["total_population"]),
            to_float(row["median_household_income"]),
            to_float(row["median_rent"]),
            to_float(row["transit_share_pct"]),
            to_float(row["pop_density_per_acre"]),
        )


def load_neighborhood_profiles(rows: list[dict[str, str]]) -> list[tuple[Any, ...]]:
    for row in rows:
        yield (
            to_int(row["community_id"]),
            to_int(row["total_population"]),
            to_float(row["avg_rent"]),
            to_float(row["crime_rate_per_1000"]),
            to_int(row["service_request_count_2024"]),
            to_int(row["transit_ridership_monthly_avg"]),
            to_int(row["affordable_unit_count"]),
        )


def load_wards(rows: list[dict[str, str]]) -> list[tuple[Any, ...]]:
    for row in rows:
        yield (to_int(row["ward_id"]), row["boundary_version"])


def load_overlap(rows: list[dict[str, str]]) -> list[tuple[Any, ...]]:
    for row in rows:
        yield (
            to_int(row["community_id"]),
            to_int(row["ward_id"]),
            to_float(row["overlap_sq_miles"]),
            to_float(row["pct_of_community_area"]),
            to_float(row["pct_of_ward"]),
        )


def load_management_companies(rows: list[dict[str, str]]) -> list[tuple[Any, ...]]:
    for row in rows:
        yield (row["management_company"], row.get("phone_number") or None)


def load_cta_lines(rows: list[dict[str, str]]) -> list[tuple[Any, ...]]:
    for row in rows:
        yield (row["line_id"], row["line_name"])


def load_cta_stations(rows: list[dict[str, str]]) -> list[tuple[Any, ...]]:
    for row in rows:
        yield (
            to_int(row["station_id"]),
            row["station_name"],
            to_bool(row.get("ada")),
            to_float(row["latitude"]),
            to_float(row["longitude"]),
            to_int(row["community_id"]),
        )


def load_serves(rows: list[dict[str, str]]) -> list[tuple[Any, ...]]:
    for row in rows:
        yield (to_int(row["station_id"]), row["line_id"])


def load_crime_aggregations(rows: list[dict[str, str]]) -> list[tuple[Any, ...]]:
    for row in rows:
        yield (
            to_int(row["community_id"]),
            to_int(row["year"]),
            to_int(row["month"]),
            row["primary_type"],
            to_int(row["crime_count"]),
        )


def load_housing_developments(
    rows: list[dict[str, str]],
    community_lookup: dict[int, dict[str, Any]],
    company_lookup: dict[str, str | None],
) -> list[tuple[Any, ...]]:
    for row in rows:
        community_id = to_int(row["community_id"])
        centroid = community_lookup.get(community_id, {})
        centroid_lat = centroid.get("centroid_lat")
        centroid_lng = centroid.get("centroid_lng")
        offset = ((to_int(row["unit_id"]) or 0) % 11 - 5) * 0.0005
        latitude = centroid_lat + offset if centroid_lat is not None else None
        longitude = centroid_lng - offset if centroid_lng is not None else None
        management_company = row.get("management_company") or None
        yield (
            to_int(row["unit_id"]),
            f"housing-{row['unit_id']}",
            row["property_name"],
            row["address"],
            row.get("property_type") or None,
            to_int(row["units"]),
            company_lookup.get(management_company),
            latitude,
            longitude,
            community_id,
            management_company,
        )


def load_ridership_monthly(rows: list[dict[str, str]]) -> list[tuple[Any, ...]]:
    grouped: dict[tuple[int, int, int], dict[str, float]] = defaultdict(dict)
    for row in rows:
        station_id = to_int(row["station_id"])
        year = to_int(row["year"])
        month = to_int(row["month"])
        grouped[(station_id, year, month)][row["day_type"]] = to_float(row["rides"]) or 0.0

    for (station_id, year, month), values in grouped.items():
        day_counts = count_month_days(year, month)
        weekday = values.get("W")
        saturday = values.get("A")
        sunday = values.get("U")
        month_total = 0
        if weekday is not None:
            month_total += round(weekday * day_counts["W"])
        if saturday is not None:
            month_total += round(saturday * day_counts["A"])
        if sunday is not None:
            month_total += round(sunday * day_counts["U"])
        yield (
            station_id,
            month_beginning(year, month),
            weekday,
            saturday,
            sunday,
            int(month_total),
        )


def load_service_requests(rows: list[dict[str, str]]) -> list[tuple[Any, ...]]:
    for row in rows:
        community_id = to_int(row["community_id"])
        base = max(1, min(8, round((to_int(row["service_request_count_2024"]) or 0) / 3000)))
        for index in range(base):
            created = datetime(2025, 1, 1) + timedelta(days=((community_id * 11) + index * 17) % 365, hours=index * 3)
            closed = created + timedelta(hours=1 + ((community_id + index) % 36))
            yield (
                f"SYN-{community_id:02d}-{index + 1:04d}",
                "Synthetic demo request",
                created,
                closed,
                "Closed",
                None,
                None,
                community_id,
                "OPEN_DATA",
            )


def load_crime_records(rows: list[dict[str, str]]) -> Iterable[tuple[Any, ...]]:
    crime_id = 1
    for row in rows:
        if to_int(row["year"]) != 2025:
            continue
        community_id = to_int(row["community_id"])
        year = to_int(row["year"])
        month = to_int(row["month"])
        crime_count = to_int(row["crime_count"]) or 0
        crime_date = datetime(year, month, 1)
        for index in range(crime_count):
            yield (
                crime_id,
                f"DEMO-{community_id}-{year}-{month:02d}-{index + 1:05d}",
                crime_date,
                row["primary_type"],
                "Synthetic demo record",
                f"Aggregated demo row {index + 1}",
                0,
                0,
                community_id,
            )
            crime_id += 1


def build_snapshot(cursor) -> None:
    cursor.execute("TRUNCATE TABLE neighborhood_profile_snapshot")
    cursor.execute(
        """
        INSERT INTO neighborhood_profile_snapshot (
            community_id,
            community_name,
            cmap_release_year,
            acs_estimate_period,
            population,
            median_household_income,
            unemployment_rate,
            pct_bachelors,
            housing_cost_burden_30plus_pct,
            crime_incidents_2025,
            crime_incidents_per_1000_population_estimate_2025,
            reported_city_supported_units_snapshot,
            rail_station_count_snapshot,
            rail_station_density_snapshot,
            rail_entries_2025,
            avg_closed_311_response_hours_2025,
            refreshed_at
        )
        SELECT
            ca.community_id,
            ca.name AS community_name,
            2025 AS cmap_release_year,
            '2025 ACS' AS acs_estimate_period,
            cp.total_population AS population,
            cp.median_household_income,
            NULL AS unemployment_rate,
            NULL AS pct_bachelors,
            NULL AS housing_cost_burden_30plus_pct,
            COALESCE(cr.crime_incidents_2025, 0) AS crime_incidents_2025,
            ROUND(
                COALESCE(cr.crime_incidents_2025, 0) * 1000.0 / NULLIF(cp.total_population, 0),
                2
            ) AS crime_incidents_per_1000_population_estimate_2025,
            COALESCE(h.reported_city_supported_units_snapshot, 0) AS reported_city_supported_units_snapshot,
            COALESCE(st.rail_station_count_snapshot, 0) AS rail_station_count_snapshot,
            ROUND(
                COALESCE(st.rail_station_count_snapshot, 0) / NULLIF(ca.area_sq_miles, 0),
                2
            ) AS rail_station_density_snapshot,
            COALESCE(rr.rail_entries_2025, 0) AS rail_entries_2025,
            sr.avg_closed_311_response_hours_2025,
            CURRENT_TIMESTAMP
        FROM community_areas ca
        LEFT JOIN census_profiles cp
            ON cp.community_id = ca.community_id
        LEFT JOIN (
            SELECT community_id, COUNT(*) AS crime_incidents_2025
            FROM crime_records
            WHERE crime_date >= '2025-01-01'
              AND crime_date < '2026-01-01'
            GROUP BY community_id
        ) cr
            ON cr.community_id = ca.community_id
        LEFT JOIN (
            SELECT community_id, SUM(COALESCE(reported_unit_count, 0)) AS reported_city_supported_units_snapshot
            FROM housing_developments
            GROUP BY community_id
        ) h
            ON h.community_id = ca.community_id
        LEFT JOIN (
            SELECT community_id, COUNT(*) AS rail_station_count_snapshot
            FROM cta_rail_stations
            WHERE community_id IS NOT NULL
            GROUP BY community_id
        ) st
            ON st.community_id = ca.community_id
        LEFT JOIN (
            SELECT rs.community_id, SUM(rr.month_total) AS rail_entries_2025
            FROM rail_ridership_monthly rr
            JOIN cta_rail_stations rs
                ON rs.station_id = rr.station_id
            WHERE rr.month_beginning >= '2025-01-01'
              AND rr.month_beginning < '2026-01-01'
              AND rs.community_id IS NOT NULL
            GROUP BY rs.community_id
        ) rr
            ON rr.community_id = ca.community_id
        LEFT JOIN (
            SELECT community_id, ROUND(AVG(TIMESTAMPDIFF(MINUTE, created_date, closed_date)) / 60.0, 2)
                AS avg_closed_311_response_hours_2025
            FROM service_requests
            WHERE record_source = 'OPEN_DATA'
              AND created_date >= '2025-01-01'
              AND created_date < '2026-01-01'
              AND closed_date IS NOT NULL
              AND closed_date >= created_date
            GROUP BY community_id
        ) sr
            ON sr.community_id = ca.community_id
        """
    )


def verify_counts(cursor) -> None:
    tables = (
        "community_areas",
        "census_profiles",
        "neighborhood_profiles",
        "cta_rail_stations",
        "crime_aggregations",
        "crime_records",
        "housing_developments",
        "rail_ridership_monthly",
        "service_requests",
        "neighborhood_profile_snapshot",
    )
    counts: dict[str, int] = {}
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) AS row_count FROM `{table}`")
        counts[table] = cursor.fetchone()["row_count"]

    for table, row_count in counts.items():
        print(f"{table}: {row_count}")

    snapshot_count = counts["neighborhood_profile_snapshot"]
    if snapshot_count != 77:
        raise RuntimeError(f"Expected 77 snapshot rows, found {snapshot_count}")


def verify_api(base_url: str) -> None:
    if not base_url:
        print("API_BASE_URL not set; skipping HTTP verification.")
        return

    import requests

    response = requests.get(f"{base_url.rstrip('/')}/api/neighborhoods", timeout=30)
    response.raise_for_status()
    rows = response.json()
    if len(rows) != 77:
        raise RuntimeError(f"Expected /api/neighborhoods to return 77 rows, got {len(rows)}")
    print(f"Verified {base_url.rstrip('/')}/api/neighborhoods returned 77 rows")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--schema-file",
        default=str(SCHEMA_SQL),
        help="Path to the demo schema SQL file.",
    )
    args = parser.parse_args()

    for variable in ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE"):
        if variable not in os.environ:
            raise SystemExit(f"Missing required environment variable: {variable}")

    connection = connect_server()
    cursor = connection.cursor(dictionary=True)
    try:
        ensure_database(cursor, os.environ["MYSQL_DATABASE"])
        drop_demo_objects(cursor)
        connection.commit()
        execute_sql_file(cursor, Path(args.schema_file))
        connection.commit()

        community_rows = read_csv_rows(DATA_DIR / "community_areas.csv")
        census_rows = read_csv_rows(DATA_DIR / "census_profiles.csv")
        neighborhood_rows = read_csv_rows(DATA_DIR / "neighborhood_profiles.csv")
        ward_rows = read_csv_rows(DATA_DIR / "wards.csv")
        overlap_rows = read_csv_rows(DATA_DIR / "community_area_ward_overlap.csv")
        company_rows = read_csv_rows(DATA_DIR / "management_companies.csv")
        line_rows = read_csv_rows(DATA_DIR / "cta_lines.csv")
        station_rows = read_csv_rows(DATA_DIR / "cta_rail_stations.csv")
        serve_rows = read_csv_rows(DATA_DIR / "serves.csv")
        crime_agg_rows = read_csv_rows(DATA_DIR / "crime_aggregations.csv")
        housing_rows = read_csv_rows(DATA_DIR / "housing_units.csv")
        ridership_rows = read_csv_rows(DATA_DIR / "rail_ridership.csv")

        community_lookup = {
            to_int(row["community_id"]): {
                "centroid_lat": to_float(row["centroid_lat"]),
                "centroid_lng": to_float(row["centroid_lng"]),
            }
            for row in community_rows
        }
        company_lookup = {
            row["management_company"]: row.get("phone_number") or None for row in company_rows
        }

        print("Loading demo tables from processed CSV files...")
        insert_rows(cursor, "community_areas", ["community_id", "name", "centroid_lat", "centroid_lng", "area_sq_miles"], load_community_areas(community_rows), 500)
        insert_rows(cursor, "census_profiles", ["community_id", "total_population", "median_household_income", "median_rent", "transit_share_pct", "pop_density_per_acre"], load_census_profiles(census_rows), 500)
        insert_rows(cursor, "neighborhood_profiles", ["community_id", "total_population", "avg_rent", "crime_rate_per_1000", "service_request_count_2024", "transit_ridership_monthly_avg", "affordable_unit_count"], load_neighborhood_profiles(neighborhood_rows), 500)
        insert_rows(cursor, "wards", ["ward_id", "boundary_version"], load_wards(ward_rows), 500)
        insert_rows(cursor, "community_area_ward_overlap", ["community_id", "ward_id", "overlap_sq_miles", "pct_of_community_area", "pct_of_ward"], load_overlap(overlap_rows), 500)
        insert_rows(cursor, "management_companies", ["management_company", "phone_number"], load_management_companies(company_rows), 500)
        insert_rows(cursor, "cta_lines", ["line_id", "line_name"], load_cta_lines(line_rows), 100)
        insert_rows(cursor, "cta_rail_stations", ["station_id", "station_name", "ada_accessible", "latitude", "longitude", "community_id"], load_cta_stations(station_rows), 500)
        insert_rows(cursor, "serves", ["station_id", "line_id"], load_serves(serve_rows), 500)
        insert_rows(cursor, "crime_aggregations", ["community_id", "year", "month", "primary_type", "crime_count"], load_crime_aggregations(crime_agg_rows), 2000)
        insert_rows(cursor, "housing_developments", ["development_id", "source_record_key", "property_name", "address", "raw_property_type", "reported_unit_count", "contact_phone", "latitude", "longitude", "community_id", "management_company"], load_housing_developments(housing_rows, community_lookup, company_lookup), 500)
        insert_rows(cursor, "rail_ridership_monthly", ["station_id", "month_beginning", "avg_weekday_rides", "avg_saturday_rides", "avg_sunday_holiday_rides", "month_total"], load_ridership_monthly(ridership_rows), 1000)
        insert_rows(cursor, "service_requests", ["source_sr_number", "request_type", "created_date", "closed_date", "status", "street_address", "zip_code", "community_id", "record_source"], load_service_requests(neighborhood_rows), 1000)
        insert_rows(cursor, "crime_records", ["crime_id", "case_number", "crime_date", "primary_type", "description", "location_description", "arrest", "domestic", "community_id"], load_crime_records(crime_agg_rows), 2000)
        connection.commit()

        build_snapshot(cursor)
        connection.commit()

        verify_counts(cursor)
        connection.commit()

        connection.autocommit = True
        cursor.execute("SELECT COUNT(*) AS row_count FROM neighborhood_profile_snapshot")
        print(f"Snapshot rows: {cursor.fetchone()['row_count']}")
    finally:
        cursor.close()
        connection.close()

    verify_api(os.environ.get("API_BASE_URL", "").strip())


if __name__ == "__main__":
    main()
