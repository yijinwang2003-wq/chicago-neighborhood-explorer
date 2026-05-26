"""SQL queries for the Streamlit app.

This module targets the final Step 3 report schema: 12 base tables plus the
three analytical views defined in ``sql/02_create_views.sql``.
"""

import warnings

import pandas as pd

warnings.filterwarnings(
    "ignore",
    message="pandas only supports SQLAlchemy connectable.*",
    category=UserWarning,
)


def query_affordable_safe(conn, min_units: int = 10):
    """Find areas with below-average 2025 crime and enough affordable units."""
    sql = """
        SELECT community_id,
               community_name,
               crime_incidents_per_1000_population_estimate_2025 AS crime_rate,
               reported_city_supported_units_snapshot AS reported_units,
               median_household_income,
               avg_closed_311_response_hours_2025 AS avg_311_hours
        FROM vw_neighborhood_profile
        WHERE crime_incidents_per_1000_population_estimate_2025 < (
            SELECT AVG(crime_incidents_per_1000_population_estimate_2025)
            FROM vw_neighborhood_profile
        )
          AND reported_city_supported_units_snapshot >= %s
        ORDER BY crime_rate ASC, reported_units DESC
    """
    return pd.read_sql(sql, conn, params=(min_units,))


def query_housing_near_transit(conn, max_distance_meters: int = 3000, top_n: int = 100):
    """Calculate affordable-housing distance to CTA rail stations at query time."""
    sql = """
        WITH candidate_distances AS (
            SELECT h.development_id,
                   h.property_name,
                   h.raw_property_type,
                   h.reported_unit_count,
                   h.address,
                   ca.name AS community_area,
                   s.station_id,
                   s.station_name,
                   ST_Distance_Sphere(
                       POINT(h.longitude, h.latitude),
                       POINT(s.longitude, s.latitude)
                   ) AS distance_meters
            FROM housing_developments h
            JOIN community_areas ca
                ON h.community_id = ca.community_id
            JOIN cta_rail_stations s
                ON s.community_id IS NOT NULL
               AND s.latitude IS NOT NULL
               AND s.longitude IS NOT NULL
            WHERE h.latitude IS NOT NULL
              AND h.longitude IS NOT NULL
        )
        SELECT cd.development_id,
               cd.property_name,
               cd.raw_property_type,
               cd.reported_unit_count,
               cd.address,
               cd.community_area,
               cd.station_name,
               GROUP_CONCAT(DISTINCT l.line_name ORDER BY l.line_name SEPARATOR ', ')
                   AS rail_lines,
               ROUND(cd.distance_meters, 1) AS distance_meters
        FROM candidate_distances cd
        LEFT JOIN serves sv
            ON cd.station_id = sv.station_id
        LEFT JOIN cta_lines l
            ON sv.line_id = l.line_id
        WHERE cd.distance_meters <= %s
        GROUP BY cd.development_id, cd.property_name, cd.raw_property_type,
                 cd.reported_unit_count, cd.address, cd.community_area,
                 cd.station_name, cd.distance_meters
        ORDER BY cd.distance_meters, cd.property_name
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(max_distance_meters, top_n))


def query_transit_usage(conn):
    """Compare 2025 CTA rail entries by community area."""
    sql = """
        SELECT community_id,
               community_name,
               rail_station_count_snapshot AS rail_station_count,
               rail_entries_2025,
               rail_station_density_snapshot AS stations_per_sq_mile
        FROM vw_neighborhood_profile
        WHERE rail_entries_2025 > 0
        ORDER BY rail_entries_2025 DESC
    """
    return pd.read_sql(sql, conn)


def query_high_demand_efficient(conn, max_avg_hours: int = 720):
    """Find high-volume 2025 311 areas with response time under a threshold."""
    sql = """
        WITH area_stats AS (
            SELECT community_id,
                   COUNT(*) AS total_requests,
                   ROUND(AVG(TIMESTAMPDIFF(MINUTE, created_date, closed_date)) / 60.0, 2)
                       AS avg_response_hours
            FROM service_requests
            WHERE record_source = 'OPEN_DATA'
              AND created_date >= '2025-01-01'
              AND created_date < '2026-01-01'
              AND closed_date IS NOT NULL
              AND closed_date >= created_date
            GROUP BY community_id
        )
        SELECT ca.community_id,
               ca.name AS community_area,
               s.total_requests,
               s.avg_response_hours
        FROM area_stats s
        JOIN community_areas ca
            ON ca.community_id = s.community_id
        WHERE s.total_requests > (SELECT AVG(total_requests) FROM area_stats)
          AND s.avg_response_hours <= %s
        ORDER BY s.avg_response_hours ASC, s.total_requests DESC
    """
    return pd.read_sql(sql, conn, params=(max_avg_hours,))


def query_most_accessible(conn, top_n: int = 15):
    """Rank community areas by rail-station density."""
    sql = """
        SELECT community_id,
               community_name,
               rail_station_count_snapshot AS num_stations,
               rail_station_density_snapshot AS stations_per_sq_mile,
               rail_entries_2025
        FROM vw_neighborhood_profile
        WHERE rail_station_count_snapshot > 0
        ORDER BY stations_per_sq_mile DESC, rail_entries_2025 DESC
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(top_n,))


def query_crime_near_housing(conn, min_housing_units: int = 5):
    """Find high-crime areas that also contain affordable housing units."""
    sql = """
        SELECT community_id,
               community_name,
               crime_incidents_2025,
               crime_incidents_per_1000_population_estimate_2025 AS crime_rate,
               reported_city_supported_units_snapshot AS affordable_units
        FROM vw_neighborhood_profile
        WHERE crime_incidents_2025 > (
            SELECT AVG(crime_incidents_2025)
            FROM vw_neighborhood_profile
        )
          AND reported_city_supported_units_snapshot >= %s
        ORDER BY crime_incidents_2025 DESC, affordable_units DESC
    """
    return pd.read_sql(sql, conn, params=(min_housing_units,))


def query_transit_popularity(conn, top_n: int = 10):
    """Identify CTA rail stations with the highest 2025 rail entries."""
    sql = """
        SELECT s.station_id,
               s.station_name,
               ca.name AS community_area,
               SUM(r.month_total) AS rail_entries_2025,
               ROUND(AVG(r.avg_weekday_rides), 1) AS avg_weekday_rides
        FROM rail_ridership_monthly r
        JOIN cta_rail_stations s
            ON s.station_id = r.station_id
        LEFT JOIN community_areas ca
            ON ca.community_id = s.community_id
        WHERE r.month_beginning >= '2025-01-01'
          AND r.month_beginning < '2026-01-01'
        GROUP BY s.station_id, s.station_name, ca.name
        ORDER BY rail_entries_2025 DESC
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(top_n,))


def query_service_delays(conn, top_n: int = 15):
    """Find community areas with the longest average 2025 311 response times."""
    sql = """
        SELECT p.community_id,
               p.community_name,
               COUNT(sr.service_request_id) AS closed_request_count,
               p.avg_closed_311_response_hours_2025 AS avg_response_hours
        FROM vw_neighborhood_profile p
        JOIN service_requests sr
            ON sr.community_id = p.community_id
        WHERE sr.record_source = 'OPEN_DATA'
          AND sr.created_date >= '2025-01-01'
          AND sr.created_date < '2026-01-01'
          AND sr.closed_date IS NOT NULL
          AND sr.closed_date >= sr.created_date
          AND p.avg_closed_311_response_hours_2025 IS NOT NULL
        GROUP BY p.community_id, p.community_name, p.avg_closed_311_response_hours_2025
        ORDER BY avg_response_hours DESC
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(top_n,))


def query_demographics_vs_crime(conn):
    """Show income, population, and 2025 crime rate by community area."""
    sql = """
        SELECT community_id,
               community_name,
               population,
               median_household_income AS median_income,
               crime_incidents_2025,
               crime_incidents_per_1000_population_estimate_2025 AS crime_rate
        FROM vw_neighborhood_profile
        ORDER BY median_income DESC
    """
    return pd.read_sql(sql, conn)


def query_neighborhood_ranking(conn, top_n: int = 20):
    """Rank areas with a simple normalized score across report indicators."""
    sql = """
        WITH raw AS (
            SELECT community_id,
                   community_name,
                   COALESCE(crime_incidents_per_1000_population_estimate_2025, 0)
                       AS crime_rate,
                   COALESCE(reported_city_supported_units_snapshot, 0)
                       AS affordable_units,
                   COALESCE(rail_station_density_snapshot, 0)
                       AS transit_density,
                   COALESCE(avg_closed_311_response_hours_2025, 9999)
                       AS avg_resp_hours
            FROM vw_neighborhood_profile
        ),
        bounds AS (
            SELECT MIN(crime_rate) AS cr_min, MAX(crime_rate) AS cr_max,
                   MIN(affordable_units) AS au_min, MAX(affordable_units) AS au_max,
                   MIN(transit_density) AS td_min, MAX(transit_density) AS td_max,
                   MIN(avg_resp_hours) AS ar_min, MAX(avg_resp_hours) AS ar_max
            FROM raw
        )
        SELECT r.community_id,
               r.community_name,
               ROUND(r.crime_rate, 2) AS crime_rate,
               r.affordable_units,
               ROUND(r.transit_density, 2) AS transit_density,
               ROUND(r.avg_resp_hours, 1) AS avg_response_hours,
               ROUND((
                   (1 - (r.crime_rate - b.cr_min) / NULLIF(b.cr_max - b.cr_min, 0))
                 + ((r.affordable_units - b.au_min) / NULLIF(b.au_max - b.au_min, 0))
                 + ((r.transit_density - b.td_min) / NULLIF(b.td_max - b.td_min, 0))
                 + (1 - (r.avg_resp_hours - b.ar_min) / NULLIF(b.ar_max - b.ar_min, 0))
               ) / 4, 3) AS neighborhood_score
        FROM raw r, bounds b
        ORDER BY neighborhood_score DESC
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(top_n,))


def query_housing_availability(conn):
    """Count affordable housing developments and units by community area."""
    sql = """
        SELECT ca.community_id,
               ca.name AS community_area,
               COUNT(h.development_id) AS num_developments,
               COALESCE(SUM(h.reported_unit_count), 0) AS reported_units
        FROM community_areas ca
        LEFT JOIN housing_developments h
            ON h.community_id = ca.community_id
        GROUP BY ca.community_id, ca.name
        ORDER BY reported_units DESC
    """
    return pd.read_sql(sql, conn)


def query_ward_overlap(conn, ward_id: int = 8):
    """Show community areas that overlap a selected Chicago ward."""
    sql = """
        SELECT ward_id,
               community_id,
               community_name,
               ROUND(overlap_sq_miles, 4) AS overlap_sq_miles,
               ROUND(pct_of_ward, 2) AS pct_of_ward,
               ROUND(pct_of_community_area, 2) AS pct_of_community_area,
               crime_incidents_per_1000_population_estimate_2025 AS crime_rate,
               housing_cost_burden_30plus_pct AS cost_burden_pct,
               avg_closed_311_response_hours_2025 AS avg_311_hours
        FROM vw_ward_community_profile
        WHERE ward_id = %s
        ORDER BY pct_of_ward DESC, community_name
    """
    return pd.read_sql(sql, conn, params=(ward_id,))


def insert_service_request(
    conn,
    request_type: str,
    community_id: int,
    street_address: str = None,
    zip_code: str = None,
    status: str = "Open",
):
    """Insert one local GUI-created 311 request into the final report schema."""
    sql = """
        INSERT INTO service_requests
            (source_sr_number, request_type, created_date, closed_date,
             status, street_address, zip_code, community_id, record_source)
        VALUES
            (NULL, %s, NOW(), NULL, %s, %s, %s, %s, 'GUI_INPUT')
    """
    cursor = conn.cursor()
    cursor.execute(sql, (request_type, status, street_address, zip_code, community_id))
    conn.commit()
    inserted_id = cursor.lastrowid
    cursor.close()
    return inserted_id


def get_community_areas(conn):
    """Return all 77 community areas as a DataFrame."""
    return pd.read_sql(
        "SELECT community_id, name FROM community_areas ORDER BY name",
        conn,
    )


def get_wards(conn):
    """Return all 50 wards as a DataFrame."""
    return pd.read_sql(
        "SELECT ward_id FROM wards ORDER BY ward_id",
        conn,
    )
