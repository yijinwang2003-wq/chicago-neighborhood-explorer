"""Read-only MySQL queries used by FastAPI endpoints."""

from collections.abc import Sequence
from typing import Any

from mysql.connector import MySQLConnection


PROFILE_COLUMNS = """
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
    avg_closed_311_response_hours_2025
"""


def fetch_all(conn: MySQLConnection, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()


def fetch_one(conn: MySQLConnection, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone()
    finally:
        cursor.close()


def list_neighborhoods(conn: MySQLConnection) -> list[dict[str, Any]]:
    return fetch_all(
        conn,
        f"""
        SELECT {PROFILE_COLUMNS}
        FROM vw_neighborhood_profile
        ORDER BY community_name
        """,
    )


def get_neighborhood(conn: MySQLConnection, community_id: int) -> dict[str, Any] | None:
    return fetch_one(
        conn,
        f"""
        SELECT {PROFILE_COLUMNS}
        FROM vw_neighborhood_profile
        WHERE community_id = %s
        """,
        (community_id,),
    )


def get_crime_breakdown(conn: MySQLConnection, community_id: int) -> list[dict[str, Any]]:
    return fetch_all(
        conn,
        """
        SELECT crime_month, crime_type, crime_count
        FROM vw_crime_aggregation
        WHERE community_id = %s
          AND crime_year = 2025
        ORDER BY crime_month, crime_count DESC, crime_type
        """,
        (community_id,),
    )


def get_transit_stations(conn: MySQLConnection, community_id: int) -> list[dict[str, Any]]:
    return fetch_all(
        conn,
        """
        SELECT
            rs.station_id,
            rs.station_name,
            rs.ada_accessible,
            GROUP_CONCAT(DISTINCT l.line_name ORDER BY l.line_name SEPARATOR ', ') AS rail_lines,
            COALESCE(SUM(rr.month_total), 0) AS total_entries_2025,
            ROUND(AVG(rr.avg_weekday_rides), 1) AS avg_weekday_rides_2025
        FROM cta_rail_stations rs
        LEFT JOIN serves sv
            ON sv.station_id = rs.station_id
        LEFT JOIN cta_lines l
            ON l.line_id = sv.line_id
        LEFT JOIN rail_ridership_monthly rr
            ON rr.station_id = rs.station_id
           AND rr.month_beginning >= '2025-01-01'
           AND rr.month_beginning < '2026-01-01'
        WHERE rs.community_id = %s
        GROUP BY rs.station_id, rs.station_name, rs.ada_accessible
        ORDER BY rs.station_name
        """,
        (community_id,),
    )


def compare_neighborhoods(conn: MySQLConnection, community_ids: Sequence[int]) -> list[dict[str, Any]]:
    placeholders = ", ".join(["%s"] * len(community_ids))
    return fetch_all(
        conn,
        f"""
        SELECT {PROFILE_COLUMNS}
        FROM vw_neighborhood_profile
        WHERE community_id IN ({placeholders})
        ORDER BY FIELD(community_id, {placeholders})
        """,
        tuple(community_ids) + tuple(community_ids),
    )
