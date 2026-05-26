#!/usr/bin/env python3
"""Load processed CSV files into MySQL using the final Step 3 schema."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import mysql.connector


DEFAULT_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
DEFAULT_DATABASE = "chicago_neighborhood"

TABLE_ORDER = [
    "community_areas",
    "wards",
    "community_area_ward_overlap",
    "census_profiles",
    "management_companies",
    "housing_developments",
    "crime_records",
    "cta_rail_stations",
    "cta_lines",
    "serves",
    "rail_ridership_monthly",
    "service_requests",
]

LOAD_SPECS = {
    "community_areas": {
        "file": "community_areas.csv",
        "columns": "(@community_id,@name,@centroid_lat,@centroid_lng,@area_sq_miles)",
        "set": """
            community_id = NULLIF(@community_id, ''),
            name = NULLIF(@name, ''),
            centroid_lat = NULLIF(@centroid_lat, ''),
            centroid_lng = NULLIF(@centroid_lng, ''),
            area_sq_miles = NULLIF(@area_sq_miles, '')
        """,
    },
    "wards": {
        "file": "wards.csv",
        "columns": "(@ward_id,@boundary_version)",
        "set": """
            ward_id = NULLIF(@ward_id, ''),
            boundary_version = COALESCE(NULLIF(@boundary_version, ''), '2023-present')
        """,
    },
    "community_area_ward_overlap": {
        "file": "community_area_ward_overlap.csv",
        "columns": "(@community_id,@ward_id,@overlap_sq_miles,@pct_of_community_area,@pct_of_ward)",
        "set": """
            community_id = NULLIF(@community_id, ''),
            ward_id = NULLIF(@ward_id, ''),
            overlap_sq_miles = NULLIF(@overlap_sq_miles, ''),
            pct_of_community_area = NULLIF(@pct_of_community_area, ''),
            pct_of_ward = NULLIF(@pct_of_ward, '')
        """,
    },
    "census_profiles": {
        "file": "census_profiles.csv",
        "columns": """
            (@community_id,@cmap_release_year,@acs_estimate_period,@population,
             @median_household_income,@median_age,@unemployment_rate,@pct_bachelors,
             @housing_cost_burden_30plus_pct)
        """,
        "set": """
            community_id = NULLIF(@community_id, ''),
            cmap_release_year = NULLIF(@cmap_release_year, ''),
            acs_estimate_period = NULLIF(@acs_estimate_period, ''),
            population = NULLIF(@population, ''),
            median_household_income = NULLIF(@median_household_income, ''),
            median_age = NULLIF(@median_age, ''),
            unemployment_rate = NULLIF(@unemployment_rate, ''),
            pct_bachelors = NULLIF(@pct_bachelors, ''),
            housing_cost_burden_30plus_pct = NULLIF(@housing_cost_burden_30plus_pct, '')
        """,
    },
    "management_companies": {
        "file": "management_companies.csv",
        "columns": "(@company_id,@company_name)",
        "set": """
            company_id = NULLIF(@company_id, ''),
            company_name = NULLIF(@company_name, '')
        """,
    },
    "housing_developments": {
        "file": "housing_developments.csv",
        "columns": """
            (@development_id,@source_record_key,@property_name,@address,@raw_property_type,
             @reported_unit_count,@contact_phone,@latitude,@longitude,@community_id,@company_id)
        """,
        "set": """
            development_id = NULLIF(@development_id, ''),
            source_record_key = NULLIF(@source_record_key, ''),
            property_name = NULLIF(@property_name, ''),
            address = NULLIF(@address, ''),
            raw_property_type = NULLIF(@raw_property_type, ''),
            reported_unit_count = NULLIF(@reported_unit_count, ''),
            contact_phone = NULLIF(@contact_phone, ''),
            latitude = NULLIF(@latitude, ''),
            longitude = NULLIF(@longitude, ''),
            community_id = NULLIF(@community_id, ''),
            company_id = NULLIF(@company_id, '')
        """,
    },
    "crime_records": {
        "file": "crime_records.csv",
        "columns": """
            (@crime_id,@case_number,@crime_date,@primary_type,@description,
             @location_description,@arrest,@domestic,@latitude,@longitude,@community_id)
        """,
        "set": """
            crime_id = NULLIF(@crime_id, ''),
            case_number = NULLIF(@case_number, ''),
            crime_date = NULLIF(@crime_date, ''),
            primary_type = NULLIF(@primary_type, ''),
            description = NULLIF(@description, ''),
            location_description = NULLIF(@location_description, ''),
            arrest = CASE LOWER(@arrest)
                WHEN '1' THEN 1 WHEN 'true' THEN 1
                WHEN '0' THEN 0 WHEN 'false' THEN 0
                ELSE NULL END,
            domestic = CASE LOWER(@domestic)
                WHEN '1' THEN 1 WHEN 'true' THEN 1
                WHEN '0' THEN 0 WHEN 'false' THEN 0
                ELSE NULL END,
            latitude = NULLIF(@latitude, ''),
            longitude = NULLIF(@longitude, ''),
            community_id = NULLIF(@community_id, '')
        """,
    },
    "cta_rail_stations": {
        "file": "cta_rail_stations.csv",
        "columns": "(@station_id,@station_name,@ada_accessible,@latitude,@longitude,@community_id)",
        "set": """
            station_id = NULLIF(@station_id, ''),
            station_name = NULLIF(@station_name, ''),
            ada_accessible = CASE LOWER(@ada_accessible)
                WHEN '1' THEN 1 WHEN 'true' THEN 1
                WHEN '0' THEN 0 WHEN 'false' THEN 0
                ELSE NULL END,
            latitude = NULLIF(@latitude, ''),
            longitude = NULLIF(@longitude, ''),
            community_id = NULLIF(@community_id, '')
        """,
    },
    "cta_lines": {
        "file": "cta_lines.csv",
        "columns": "(@line_id,@line_name)",
        "set": """
            line_id = NULLIF(@line_id, ''),
            line_name = NULLIF(@line_name, '')
        """,
    },
    "serves": {
        "file": "serves.csv",
        "columns": "(@station_id,@line_id)",
        "set": """
            station_id = NULLIF(@station_id, ''),
            line_id = NULLIF(@line_id, '')
        """,
    },
    "rail_ridership_monthly": {
        "file": "rail_ridership_monthly.csv",
        "columns": """
            (@station_id,@month_beginning,@avg_weekday_rides,@avg_saturday_rides,
             @avg_sunday_holiday_rides,@month_total)
        """,
        "set": """
            station_id = NULLIF(@station_id, ''),
            month_beginning = NULLIF(@month_beginning, ''),
            avg_weekday_rides = NULLIF(@avg_weekday_rides, ''),
            avg_saturday_rides = NULLIF(@avg_saturday_rides, ''),
            avg_sunday_holiday_rides = NULLIF(@avg_sunday_holiday_rides, ''),
            month_total = NULLIF(@month_total, '')
        """,
    },
    "service_requests": {
        "file": "service_requests.csv",
        "columns": """
            (@source_sr_number,@request_type,@created_date,@closed_date,@status,
             @street_address,@zip_code,@community_id,@record_source)
        """,
        "set": """
            source_sr_number = NULLIF(@source_sr_number, ''),
            request_type = NULLIF(@request_type, ''),
            created_date = NULLIF(@created_date, ''),
            closed_date = NULLIF(@closed_date, ''),
            status = NULLIF(@status, ''),
            street_address = NULLIF(@street_address, ''),
            zip_code = NULLIF(@zip_code, ''),
            community_id = NULLIF(@community_id, ''),
            record_source = COALESCE(NULLIF(@record_source, ''), 'OPEN_DATA')
        """,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("MYSQL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MYSQL_PORT", "3306")))
    parser.add_argument("--user", default=os.getenv("MYSQL_USER", "root"))
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--database", default=os.getenv("MYSQL_DATABASE", DEFAULT_DATABASE))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--create-schema", action="store_true")
    parser.add_argument("--create-indexes", action="store_true")
    parser.add_argument("--skip-load", action="store_true")
    parser.add_argument("--truncate", action="store_true")
    return parser.parse_args()


def sql_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "sql" / name


def connect(args: argparse.Namespace, *, database: str | None = None):
    return mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=database,
        allow_local_infile=True,
        autocommit=False,
    )


def split_sql(script: str) -> list[str]:
    cleaned_lines = []
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        cleaned_lines.append(line)
    return [statement.strip() for statement in "\n".join(cleaned_lines).split(";") if statement.strip()]


def run_sql_file(cursor, path: Path) -> None:
    for statement in split_sql(path.read_text()):
        cursor.execute(statement)


def create_schema(args: argparse.Namespace) -> None:
    with connect(args) as connection:
        cursor = connection.cursor()
        run_sql_file(cursor, sql_path("00_create_database.sql"))
        connection.commit()
    with connect(args, database=args.database) as connection:
        cursor = connection.cursor()
        run_sql_file(cursor, sql_path("01_create_tables.sql"))
        connection.commit()


def refresh_views_and_indexes(args: argparse.Namespace) -> None:
    with connect(args, database=args.database) as connection:
        cursor = connection.cursor()
        run_sql_file(cursor, sql_path("02_create_views.sql"))
        if args.create_indexes:
            run_sql_file(cursor, sql_path("03_create_indexes.sql"))
        connection.commit()


def truncate_tables(cursor) -> None:
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    for table in reversed(TABLE_ORDER):
        cursor.execute(f"TRUNCATE TABLE {table}")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")


def load_table(cursor, processed_dir: Path, table: str) -> None:
    spec = LOAD_SPECS[table]
    csv_path = (processed_dir / spec["file"]).resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing processed CSV for {table}: {csv_path}")
    path_sql = csv_path.as_posix().replace("\\", "\\\\").replace("'", "\\'")
    columns = re.sub(r"\s+", " ", spec["columns"]).strip()
    set_clause = re.sub(r"\s+", " ", spec["set"]).strip()
    sql = f"""
        LOAD DATA LOCAL INFILE '{path_sql}'
        INTO TABLE {table}
        CHARACTER SET utf8mb4
        FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
        LINES TERMINATED BY '\\n'
        IGNORE 1 ROWS
        {columns}
        SET {set_clause}
    """
    cursor.execute(sql)
    print(f"loaded {table}: {cursor.rowcount} rows")


def run_load(args: argparse.Namespace) -> None:
    with connect(args, database=args.database) as connection:
        cursor = connection.cursor()
        if args.truncate:
            truncate_tables(cursor)
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        cursor.execute("SET UNIQUE_CHECKS = 0")
        for table in TABLE_ORDER:
            load_table(cursor, args.processed_dir, table)
        cursor.execute("SET UNIQUE_CHECKS = 1")
        connection.commit()


def print_counts(args: argparse.Namespace) -> None:
    with connect(args, database=args.database) as connection:
        cursor = connection.cursor()
        for table in TABLE_ORDER:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"{table}: {cursor.fetchone()[0]}")


def main() -> int:
    args = parse_args()
    if args.create_schema:
        create_schema(args)
    if not args.skip_load:
        run_load(args)
    refresh_views_and_indexes(args)
    print_counts(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
