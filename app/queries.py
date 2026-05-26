"""

Each public function accepts a MySQL connection (or engine) as its first
argument, plus optional user-facing parameters, and returns a pandas
DataFrame ready for Streamlit display.

Schema: chicago_neighborhood
"""

import pandas as pd


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 1 — Affordable + Safe Neighborhoods
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_affordable_safe(conn, min_units: int = 10):
    """
    Find community areas where the 2025 crime rate is below the city-wide
    average AND reported affordable housing units >= *min_units*.

    Uses: vw_neighborhood_profile
    """
    sql = """
        SELECT community_id,
               community_name,
               crime_incidents_per_1000_population_estimate_2025  AS crime_rate,
               reported_city_supported_units_snapshot             AS affordable_units
        FROM   vw_neighborhood_profile
        WHERE  crime_incidents_per_1000_population_estimate_2025 < (
                   SELECT AVG(crime_incidents_per_1000_population_estimate_2025)
                   FROM   vw_neighborhood_profile
                   WHERE  crime_incidents_per_1000_population_estimate_2025 IS NOT NULL
               )
          AND  reported_city_supported_units_snapshot >= %s
        ORDER BY crime_rate ASC
    """
    return pd.read_sql(sql, conn, params=(min_units,))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 2 — Housing Near Transit
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_housing_near_transit(conn, max_distance_meters: int = 800, top_n: int = 100):
    """
    Find affordable housing developments within *max_distance_meters*
    of CTA rail stations. Distance is calculated at query time from
    housing and station coordinates.

    Uses: housing_developments, community_areas, cta_rail_stations,
          serves, cta_lines
    """
    sql = """
        WITH candidate_distances AS (
            SELECT hd.development_id,
                   hd.property_name,
                   hd.raw_property_type       AS property_type,
                   hd.reported_unit_count     AS total_units,
                   hd.address,
                   ca.name                    AS community_area,
                   rs.station_id,
                   rs.station_name,
                   ST_Distance_Sphere(
                       POINT(hd.longitude, hd.latitude),
                       POINT(rs.longitude, rs.latitude)
                   ) AS distance_meters
            FROM   housing_developments hd
            JOIN   community_areas ca
                   ON ca.community_id = hd.community_id
            CROSS JOIN cta_rail_stations rs
            WHERE  hd.latitude IS NOT NULL
              AND  hd.longitude IS NOT NULL
              AND  rs.latitude IS NOT NULL
              AND  rs.longitude IS NOT NULL
              AND  rs.community_id IS NOT NULL
        )
        SELECT cd.development_id,
               cd.property_name,
               cd.property_type,
               cd.total_units,
               cd.address,
               cd.community_area,
               cd.station_name,
               GROUP_CONCAT(DISTINCT l.line_name ORDER BY l.line_name SEPARATOR ', ')
                   AS rail_lines,
               ROUND(cd.distance_meters, 1) AS distance_meters
        FROM   candidate_distances cd
        LEFT JOIN serves sv
               ON sv.station_id = cd.station_id
        LEFT JOIN cta_lines l
               ON l.line_id = sv.line_id
        WHERE  cd.distance_meters <= %s
        GROUP BY cd.development_id,
                 cd.property_name,
                 cd.property_type,
                 cd.total_units,
                 cd.address,
                 cd.community_area,
                 cd.station_name,
                 cd.distance_meters
        ORDER BY cd.distance_meters ASC, cd.property_name, cd.station_name
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(max_distance_meters, top_n))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 3 — Transit Usage by Neighborhood
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_transit_usage(conn):
    """
    For each community area, compute total CTA rail entries and average
    weekday ridership for calendar year 2025.

    Uses: rail_ridership_monthly, cta_rail_stations, community_areas
    """
    sql = """
        SELECT ca.community_id,
               ca.name                                    AS community_area,
               COUNT(DISTINCT rs.station_id)              AS num_stations,
               SUM(rr.month_total)                        AS total_entries,
               ROUND(AVG(rr.avg_weekday_rides), 0)       AS avg_weekday_rides
        FROM   rail_ridership_monthly rr
        JOIN   cta_rail_stations rs ON rs.station_id = rr.station_id
        JOIN   community_areas ca  ON ca.community_id = rs.community_id
        WHERE  rr.month_beginning >= '2025-01-01'
          AND  rr.month_beginning <  '2026-01-01'
        GROUP BY ca.community_id, ca.name
        ORDER BY total_entries DESC
    """
    return pd.read_sql(sql, conn)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 5 — High Demand vs Service Efficiency
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_high_demand_efficient(conn, max_avg_hours: int = 720):
    """
    Find community areas with above-average 311 request volume but fast
    average response times (<= *max_avg_hours* hours) in calendar year 2025.

    Uses: service_requests, community_areas
    """
    sql = """
        WITH area_stats AS (
            SELECT community_id,
                   COUNT(*)  AS total_requests,
                   ROUND(AVG(TIMESTAMPDIFF(MINUTE, created_date, closed_date)) / 60.0, 2)
                       AS avg_response_hours
            FROM   service_requests
            WHERE  record_source = 'OPEN_DATA'
              AND  created_date >= '2025-01-01'
              AND  created_date <  '2026-01-01'
              AND  closed_date IS NOT NULL
              AND  closed_date >= created_date
            GROUP BY community_id
        )
        SELECT ca.community_id,
               ca.name               AS community_area,
               s.total_requests,
               s.avg_response_hours
        FROM   area_stats s
        JOIN   community_areas ca ON ca.community_id = s.community_id
        WHERE  s.total_requests > (SELECT AVG(total_requests) FROM area_stats)
          AND  s.avg_response_hours <= %s
        ORDER BY s.avg_response_hours ASC
    """
    return pd.read_sql(sql, conn, params=(max_avg_hours,))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 6 — Most Accessible Neighborhoods (Transit Density)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_most_accessible(conn, top_n: int = 15):
    """
    Rank community areas by transit density = CTA rail stations per
    square mile. Return the top *top_n* areas.

    Uses: cta_rail_stations, community_areas
    """
    sql = """
        SELECT ca.community_id,
               ca.name                                              AS community_area,
               COUNT(rs.station_id)                                 AS num_stations,
               ca.area_sq_miles,
               ROUND(COUNT(rs.station_id) / ca.area_sq_miles, 2)   AS stations_per_sq_mile
        FROM   community_areas ca
        LEFT JOIN cta_rail_stations rs ON rs.community_id = ca.community_id
        GROUP BY ca.community_id, ca.name, ca.area_sq_miles
        HAVING num_stations > 0
        ORDER BY stations_per_sq_mile DESC
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(top_n,))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 7 — Crime Near Housing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_crime_near_housing(conn, min_housing_units: int = 5):
    """
    Find community areas where total crime is above the city-wide average
    AND affordable housing units >= *min_housing_units* for calendar year 2025.

    Uses: crime_records, housing_developments, community_areas
    """
    sql = """
        WITH area_crime AS (
            SELECT community_id,
                   COUNT(*) AS total_crimes
            FROM   crime_records
            WHERE  crime_date >= '2025-01-01'
              AND  crime_date <  '2026-01-01'
            GROUP BY community_id
        ),
        area_housing AS (
            SELECT community_id,
                   COUNT(*)                          AS num_properties,
                   SUM(COALESCE(reported_unit_count, 0)) AS total_units
            FROM   housing_developments
            GROUP BY community_id
        )
        SELECT ca.community_id,
               ca.name              AS community_area,
               ac.total_crimes,
               ah.num_properties,
               ah.total_units       AS affordable_units
        FROM   area_crime ac
        JOIN   area_housing ah ON ah.community_id = ac.community_id
        JOIN   community_areas ca ON ca.community_id = ac.community_id
        WHERE  ac.total_crimes > (SELECT AVG(total_crimes) FROM area_crime)
          AND  ah.total_units >= %s
        ORDER BY ac.total_crimes DESC
    """
    return pd.read_sql(sql, conn, params=(min_housing_units,))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 8 — Transit Stop Popularity
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_transit_popularity(conn, top_n: int = 10):
    """
    Identify the top *top_n* transit stations with the highest total
    ridership in calendar year 2025, along with their community areas.

    Uses: rail_ridership_monthly, cta_rail_stations, community_areas
    """
    sql = """
        SELECT rs.station_id,
               rs.station_name,
               ca.name                          AS community_area,
               SUM(rr.month_total)              AS total_entries,
               ROUND(AVG(rr.avg_weekday_rides), 0) AS avg_weekday_rides
        FROM   rail_ridership_monthly rr
        JOIN   cta_rail_stations rs ON rs.station_id = rr.station_id
        LEFT JOIN community_areas ca ON ca.community_id = rs.community_id
        WHERE  rr.month_beginning >= '2025-01-01'
          AND  rr.month_beginning <  '2026-01-01'
        GROUP BY rs.station_id, rs.station_name, ca.name
        ORDER BY total_entries DESC
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(top_n,))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 9 — Service Request Delays
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_service_delays(conn, top_n: int = 15):
    """
    Find the community areas with the longest average 311 response time
    in calendar year 2025. Return the top *top_n* slowest areas.

    Uses: service_requests, community_areas
    """
    sql = """
        SELECT ca.community_id,
               ca.name                                                AS community_area,
               COUNT(*)                                               AS total_requests,
               ROUND(AVG(TIMESTAMPDIFF(MINUTE, sr.created_date, sr.closed_date)) / 60.0, 2)
                   AS avg_response_hours
        FROM   service_requests sr
        JOIN   community_areas ca ON ca.community_id = sr.community_id
        WHERE  record_source = 'OPEN_DATA'
          AND  sr.created_date >= '2025-01-01'
          AND  sr.created_date <  '2026-01-01'
          AND  sr.closed_date IS NOT NULL
          AND  sr.closed_date >= sr.created_date
        GROUP BY ca.community_id, ca.name
        ORDER BY avg_response_hours DESC
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(top_n,))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 10 — Demographics vs Crime
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_demographics_vs_crime(conn):
    """
    Show median household income alongside 2025 crime rate for each
    community area.

    Uses: vw_neighborhood_profile
    """
    sql = """
        SELECT community_id,
               community_name,
               population,
               median_household_income                                AS median_income,
               crime_incidents_per_1000_population_estimate_2025      AS crime_rate
        FROM   vw_neighborhood_profile
        WHERE  median_household_income IS NOT NULL
          AND  crime_incidents_per_1000_population_estimate_2025 IS NOT NULL
        ORDER BY median_household_income DESC
    """
    return pd.read_sql(sql, conn)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 11 — Neighborhood Profile Ranking (Composite Score)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_neighborhood_ranking(conn, top_n: int = 20):
    """
    Rank community areas with a composite livability score combining:
      • crime rate         (lower  is better → inverted)
      • affordable units   (higher is better)
      • transit density    (higher is better)
      • 311 response time  (lower  is better → inverted)

    Each dimension is min-max normalized to [0,1], then averaged.

    Uses: vw_neighborhood_profile
    """
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
            FROM   vw_neighborhood_profile
            WHERE  crime_incidents_per_1000_population_estimate_2025 IS NOT NULL
        ),
        bounds AS (
            SELECT MIN(crime_rate)       AS cr_min,  MAX(crime_rate)       AS cr_max,
                   MIN(affordable_units) AS au_min,  MAX(affordable_units) AS au_max,
                   MIN(transit_density)  AS td_min,  MAX(transit_density)  AS td_max,
                   MIN(avg_resp_hours)   AS ar_min,  MAX(avg_resp_hours)   AS ar_max
            FROM raw
        )
        SELECT r.community_id,
               r.community_name,
               r.crime_rate,
               r.affordable_units,
               ROUND(r.transit_density, 2)   AS transit_density,
               ROUND(r.avg_resp_hours, 1)    AS avg_response_hours,
               ROUND(
                   (
                     (1 - (r.crime_rate       - b.cr_min) / NULLIF(b.cr_max - b.cr_min, 0))
                   + (    (r.affordable_units - b.au_min) / NULLIF(b.au_max - b.au_min, 0))
                   + (    (r.transit_density  - b.td_min) / NULLIF(b.td_max - b.td_min, 0))
                   + (1 - (r.avg_resp_hours   - b.ar_min) / NULLIF(b.ar_max - b.ar_min, 0))
                   ) / 4
               , 3)                          AS livability_score
        FROM  raw r, bounds b
        ORDER BY livability_score DESC
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(top_n,))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 12 — Housing Availability by Area
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_housing_availability(conn):
    """
    For each community area, count affordable housing developments and
    total reported units.

    Uses: housing_developments, community_areas
    """
    sql = """
        SELECT ca.community_id,
               ca.name                                        AS community_area,
               COUNT(hd.development_id)                       AS num_properties,
               COALESCE(SUM(hd.reported_unit_count), 0)       AS total_units
        FROM   community_areas ca
        LEFT JOIN housing_developments hd ON hd.community_id = ca.community_id
        GROUP BY ca.community_id, ca.name
        ORDER BY total_units DESC
    """
    return pd.read_sql(sql, conn)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 14 — Ward Overlap Analysis
#  Uses wards + community_area_ward_overlap + vw_ward_community_profile
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_ward_overlap(conn, ward_id: int = 27):
    """
    For a selected ward, show all community areas that overlap with it,
    along with overlap size, percentages, and key neighborhood indicators.

    This query uses the second M:N relationship in our schema:
    wards <-> community_area_ward_overlap <-> community_areas

    Uses: wards, community_area_ward_overlap, vw_ward_community_profile
    """
    sql = """
        SELECT w.ward_id,
               o.community_id,
               v.community_name,
               ROUND(o.overlap_sq_miles, 4)                         AS overlap_sq_miles,
               ROUND(o.pct_of_ward, 2)                              AS pct_of_ward,
               ROUND(o.pct_of_community_area, 2)                    AS pct_of_community_area,
               v.crime_incidents_per_1000_population_estimate_2025  AS crime_rate,
               v.housing_cost_burden_30plus_pct                     AS cost_burden_pct,
               v.avg_closed_311_response_hours_2025                 AS avg_311_hours
        FROM   wards w
        JOIN   community_area_ward_overlap o
               ON o.ward_id = w.ward_id
        JOIN   vw_ward_community_profile v
               ON v.ward_id = o.ward_id
              AND v.community_id = o.community_id
        WHERE  w.ward_id = %s
        ORDER BY o.pct_of_ward DESC, v.community_name
    """
    return pd.read_sql(sql, conn, params=(ward_id,))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Insert helper — add a new 311 service request
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def insert_service_request(
    conn,
    request_type: str,
    community_id: int,
    street_address: str = None,
    zip_code: str = None,
    status: str = "Open",
):
    """
    Insert a new 311 service request via the GUI.
    source_sr_number is NULL and record_source is 'GUI_INPUT'
    per the schema design.
    Returns True on success.

    Table: service_requests
    """
    sql = """
        INSERT INTO service_requests
            (source_sr_number, request_type, created_date, closed_date,
             status, street_address, zip_code, community_id, record_source)
        VALUES (NULL, %s, NOW(), NULL, %s, %s, %s, %s, 'GUI_INPUT')
    """
    cursor = conn.cursor()
    cursor.execute(sql, (
        request_type, status, street_address, zip_code, community_id,
    ))
    conn.commit()
    cursor.close()
    return True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Utility — list community areas (for dropdowns / validation)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_community_areas(conn):
    """Return all 77 community areas as a DataFrame (for dropdowns)."""
    return pd.read_sql(
        "SELECT community_id, name FROM community_areas ORDER BY name",
        conn,
    )


def get_wards(conn):
    """Return all 50 wards as a DataFrame (for dropdowns)."""
    return pd.read_sql(
        "SELECT ward_id FROM wards ORDER BY ward_id",
        conn,
    )
