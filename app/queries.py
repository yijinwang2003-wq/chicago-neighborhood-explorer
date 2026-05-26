"""SQL queries for the Streamlit app.

This version targets the teammate-provided 14-table MySQL dataset in
``db-data/chicago_neighborhood_data``.
"""

from datetime import datetime
from random import randint
import warnings

import pandas as pd

warnings.filterwarnings(
    "ignore",
    message="pandas only supports SQLAlchemy connectable.*",
    category=UserWarning,
)


def query_affordable_safe(conn, min_units: int = 10):
    """Find areas with below-average crime rate and enough affordable units."""
    sql = """
        SELECT ca.community_id,
               ca.name AS community_name,
               np.crime_rate_per_1000 AS crime_rate,
               np.affordable_unit_count AS affordable_units,
               cp.median_rent
        FROM neighborhood_profiles np
        JOIN community_areas ca ON ca.community_id = np.community_id
        LEFT JOIN census_profiles cp ON cp.community_id = np.community_id
        WHERE np.crime_rate_per_1000 < (
            SELECT AVG(crime_rate_per_1000)
            FROM neighborhood_profiles
            WHERE crime_rate_per_1000 IS NOT NULL
        )
          AND np.affordable_unit_count >= %s
        ORDER BY np.crime_rate_per_1000 ASC, np.affordable_unit_count DESC
    """
    return pd.read_sql(sql, conn, params=(min_units,))


def query_housing_near_transit(conn, max_distance_meters: int = 800, top_n: int = 100):
    """Show affordable housing in community areas that have CTA rail stations."""
    sql = """
        WITH station_lines AS (
            SELECT rs.community_id,
                   rs.station_id,
                   rs.station_name,
                   GROUP_CONCAT(DISTINCT l.line_name ORDER BY l.line_name SEPARATOR ', ')
                       AS rail_lines
            FROM cta_rail_stations rs
            LEFT JOIN serves sv ON sv.station_id = rs.station_id
            LEFT JOIN cta_lines l ON l.line_id = sv.line_id
            WHERE rs.community_id IS NOT NULL
            GROUP BY rs.community_id, rs.station_id, rs.station_name
        )
        SELECT hu.unit_id AS development_id,
               hu.property_name,
               hu.property_type,
               hu.units AS total_units,
               hu.address,
               ca.name AS community_area,
               sl.station_name,
               sl.rail_lines
        FROM housing_units hu
        JOIN community_areas ca ON ca.community_id = hu.community_id
        JOIN station_lines sl ON sl.community_id = hu.community_id
        ORDER BY ca.name, hu.property_name, sl.station_name
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(top_n,))


def query_transit_usage(conn):
    """Compare 2025 CTA rail average ridership by community area."""
    sql = """
        SELECT ca.community_id,
               ca.name AS community_area,
               COUNT(DISTINCT rs.station_id) AS num_stations,
               ROUND(SUM(rr.rides), 0) AS summed_average_rides,
               ROUND(AVG(CASE WHEN rr.day_type = 'W' THEN rr.rides END), 0)
                   AS avg_weekday_rides
        FROM rail_ridership rr
        JOIN cta_rail_stations rs ON rs.station_id = rr.station_id
        JOIN community_areas ca ON ca.community_id = rs.community_id
        WHERE rr.year = 2025
        GROUP BY ca.community_id, ca.name
        ORDER BY summed_average_rides DESC
    """
    return pd.read_sql(sql, conn)


def query_high_demand_efficient(conn, max_avg_hours: int = 720):
    """Find high-volume 2025 311 areas with response time under a threshold."""
    sql = """
        WITH area_stats AS (
            SELECT community_id,
                   COUNT(*) AS total_requests,
                   ROUND(AVG(DATEDIFF(closed_date, created_date)) * 24.0, 2)
                       AS avg_response_hours
            FROM service_requests
            WHERE year = 2025
              AND closed_date IS NOT NULL
              AND closed_date >= created_date
            GROUP BY community_id
        )
        SELECT ca.community_id,
               ca.name AS community_area,
               s.total_requests,
               s.avg_response_hours
        FROM area_stats s
        JOIN community_areas ca ON ca.community_id = s.community_id
        WHERE s.total_requests > (SELECT AVG(total_requests) FROM area_stats)
          AND s.avg_response_hours <= %s
        ORDER BY s.avg_response_hours ASC, s.total_requests DESC
    """
    return pd.read_sql(sql, conn, params=(max_avg_hours,))


def query_most_accessible(conn, top_n: int = 15):
    """Rank community areas by rail-station density."""
    sql = """
        SELECT ca.community_id,
               ca.name AS community_area,
               COUNT(rs.station_id) AS num_stations,
               ca.area_sq_miles,
               ROUND(COUNT(rs.station_id) / ca.area_sq_miles, 2)
                   AS stations_per_sq_mile
        FROM community_areas ca
        LEFT JOIN cta_rail_stations rs ON rs.community_id = ca.community_id
        GROUP BY ca.community_id, ca.name, ca.area_sq_miles
        HAVING num_stations > 0
        ORDER BY stations_per_sq_mile DESC
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(top_n,))


def query_crime_near_housing(conn, min_housing_units: int = 5):
    """Find 2025 high-crime areas that also have affordable housing units."""
    sql = """
        WITH area_crime AS (
            SELECT community_id, SUM(crime_count) AS total_crimes
            FROM crime_aggregations
            WHERE year = 2025
            GROUP BY community_id
        ),
        area_housing AS (
            SELECT community_id,
                   COUNT(*) AS num_properties,
                   SUM(COALESCE(units, 0)) AS total_units
            FROM housing_units
            GROUP BY community_id
        )
        SELECT ca.community_id,
               ca.name AS community_area,
               ac.total_crimes,
               ah.num_properties,
               ah.total_units AS affordable_units
        FROM area_crime ac
        JOIN area_housing ah ON ah.community_id = ac.community_id
        JOIN community_areas ca ON ca.community_id = ac.community_id
        WHERE ac.total_crimes > (SELECT AVG(total_crimes) FROM area_crime)
          AND ah.total_units >= %s
        ORDER BY ac.total_crimes DESC
    """
    return pd.read_sql(sql, conn, params=(min_housing_units,))


def query_transit_popularity(conn, top_n: int = 10):
    """Identify CTA rail stations with the highest 2025 average ridership."""
    sql = """
        SELECT rs.station_id,
               rs.station_name,
               ca.name AS community_area,
               ROUND(SUM(rr.rides), 0) AS summed_average_rides,
               ROUND(AVG(CASE WHEN rr.day_type = 'W' THEN rr.rides END), 0)
                   AS avg_weekday_rides
        FROM rail_ridership rr
        JOIN cta_rail_stations rs ON rs.station_id = rr.station_id
        LEFT JOIN community_areas ca ON ca.community_id = rs.community_id
        WHERE rr.year = 2025
        GROUP BY rs.station_id, rs.station_name, ca.name
        ORDER BY summed_average_rides DESC
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(top_n,))


def query_service_delays(conn, top_n: int = 15):
    """Find community areas with the longest average 2025 311 response times."""
    sql = """
        SELECT ca.community_id,
               ca.name AS community_area,
               COUNT(*) AS total_requests,
               ROUND(AVG(DATEDIFF(sr.closed_date, sr.created_date)) * 24.0, 2)
                   AS avg_response_hours
        FROM service_requests sr
        JOIN community_areas ca ON ca.community_id = sr.community_id
        WHERE sr.year = 2025
          AND sr.closed_date IS NOT NULL
          AND sr.closed_date >= sr.created_date
        GROUP BY ca.community_id, ca.name
        ORDER BY avg_response_hours DESC
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(top_n,))


def query_demographics_vs_crime(conn):
    """Show income, population, and 2025 crime rate by community area."""
    sql = """
        WITH area_crime AS (
            SELECT community_id, SUM(crime_count) AS total_crimes
            FROM crime_aggregations
            WHERE year = 2025
            GROUP BY community_id
        )
        SELECT ca.community_id,
               ca.name AS community_name,
               cp.total_population AS population,
               cp.median_household_income AS median_income,
               ROUND(ac.total_crimes * 1000.0 / NULLIF(cp.total_population, 0), 2)
                   AS crime_rate
        FROM census_profiles cp
        JOIN community_areas ca ON ca.community_id = cp.community_id
        LEFT JOIN area_crime ac ON ac.community_id = cp.community_id
        ORDER BY cp.median_household_income DESC
    """
    return pd.read_sql(sql, conn)


def query_neighborhood_ranking(conn, top_n: int = 20):
    """Rank areas with a simple normalized score across key indicators."""
    sql = """
        WITH response AS (
            SELECT community_id,
                   AVG(DATEDIFF(closed_date, created_date)) * 24.0 AS avg_resp_hours
            FROM service_requests
            WHERE year = 2025
              AND closed_date IS NOT NULL
              AND closed_date >= created_date
            GROUP BY community_id
        ),
        stations AS (
            SELECT ca.community_id,
                   COUNT(rs.station_id) / ca.area_sq_miles AS transit_density
            FROM community_areas ca
            LEFT JOIN cta_rail_stations rs ON rs.community_id = ca.community_id
            GROUP BY ca.community_id, ca.area_sq_miles
        ),
        raw AS (
            SELECT ca.community_id,
                   ca.name AS community_name,
                   COALESCE(np.crime_rate_per_1000, 0) AS crime_rate,
                   COALESCE(np.affordable_unit_count, 0) AS affordable_units,
                   COALESCE(st.transit_density, 0) AS transit_density,
                   COALESCE(r.avg_resp_hours, 9999) AS avg_resp_hours
            FROM community_areas ca
            LEFT JOIN neighborhood_profiles np ON np.community_id = ca.community_id
            LEFT JOIN stations st ON st.community_id = ca.community_id
            LEFT JOIN response r ON r.community_id = ca.community_id
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
               ) / 4, 3) AS livability_score
        FROM raw r, bounds b
        ORDER BY livability_score DESC
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(top_n,))


def query_housing_availability(conn):
    """Count affordable housing developments and units by community area."""
    sql = """
        SELECT ca.community_id,
               ca.name AS community_area,
               COUNT(hu.unit_id) AS num_properties,
               COALESCE(SUM(hu.units), 0) AS total_units
        FROM community_areas ca
        LEFT JOIN housing_units hu ON hu.community_id = ca.community_id
        GROUP BY ca.community_id, ca.name
        ORDER BY total_units DESC
    """
    return pd.read_sql(sql, conn)


def query_ward_overlap(conn, ward_id: int = 27):
    """Show community areas that overlap a selected Chicago ward."""
    sql = """
        WITH crime_2025 AS (
            SELECT community_id, SUM(crime_count) AS total_crimes
            FROM crime_aggregations
            WHERE year = 2025
            GROUP BY community_id
        )
        SELECT o.ward_id,
               o.community_id,
               ca.name AS community_name,
               ROUND(o.overlap_sq_miles, 4) AS overlap_sq_miles,
               ROUND(o.pct_of_ward, 2) AS pct_of_ward,
               ROUND(o.pct_of_community_area, 2) AS pct_of_community_area,
               cp.median_household_income AS median_income,
               ROUND(c.total_crimes * 1000.0 / NULLIF(cp.total_population, 0), 2)
                   AS crime_rate
        FROM community_area_ward_overlap o
        JOIN community_areas ca ON ca.community_id = o.community_id
        LEFT JOIN census_profiles cp ON cp.community_id = o.community_id
        LEFT JOIN crime_2025 c ON c.community_id = o.community_id
        WHERE o.ward_id = %s
        ORDER BY o.pct_of_ward DESC, ca.name
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
    """Insert one local GUI-created 311 request into the teammate schema."""
    sr_number = f"G{datetime.now():%Y%m%d%H%M%S}{randint(0, 99):02d}"
    sql = """
        INSERT INTO service_requests
            (sr_number, community_id, created_date, closed_date,
             year, month, request_type, status)
        VALUES (
            %s, %s, CURRENT_DATE(), NULL, YEAR(CURRENT_DATE()), MONTH(CURRENT_DATE()), %s, %s
        )
    """
    cursor = conn.cursor()
    cursor.execute(sql, (sr_number, community_id, request_type, status))
    conn.commit()
    cursor.close()
    return True


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
