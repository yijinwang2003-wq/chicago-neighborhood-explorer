"""

Each public function accepts a MySQL connection (or engine) as its first
argument, plus optional user-facing parameters, and returns a pandas
DataFrame ready for Streamlit display.

"""

import pandas as pd


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 1 — Affordable + Safe Neighborhoods
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_affordable_safe(conn, min_units: int = 10):
    """
    Find community areas where the crime rate is below the city-wide
    average AND affordable housing units >= *min_units*.

    Tables: neighborhood_profiles, community_areas
    """
    sql = """
        SELECT ca.community_id,
               ca.name                      AS community_area,
               np.crime_rate_per_1000       AS crime_rate,
               np.affordable_unit_count     AS affordable_units
        FROM   neighborhood_profiles np
        JOIN   community_areas ca ON ca.community_id = np.community_id
        WHERE  np.crime_rate_per_1000 < (
                   SELECT AVG(crime_rate_per_1000)
                   FROM   neighborhood_profiles
                   WHERE  crime_rate_per_1000 IS NOT NULL
               )
          AND  np.affordable_unit_count >= %s
        ORDER BY np.crime_rate_per_1000 ASC
    """
    return pd.read_sql(sql, conn, params=(min_units,))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 2 — Housing Near Transit
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_housing_near_transit(conn, min_stops: int = 1):
    """
    Find affordable housing units in community areas that have at least
    *min_stops* CTA rail stations.

    Tables: housing_units, community_areas, cta_rail_stations
    """
    sql = """
        SELECT hu.unit_id,
               hu.property_name,
               hu.property_type,
               hu.units               AS total_units,
               hu.address,
               ca.name                AS community_area,
               stop_counts.num_stops
        FROM   housing_units hu
        JOIN   community_areas ca ON ca.community_id = hu.community_id
        JOIN   (
                   SELECT community_id, COUNT(*) AS num_stops
                   FROM   cta_rail_stations
                   WHERE  community_id IS NOT NULL
                   GROUP BY community_id
                   HAVING COUNT(*) >= %s
               ) stop_counts ON stop_counts.community_id = hu.community_id
        ORDER BY stop_counts.num_stops DESC, hu.property_name
    """
    return pd.read_sql(sql, conn, params=(min_stops,))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 3 — Transit Usage by Neighborhood
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_transit_usage(conn, year: int = 2024, day_type: str = "W"):
    """
    For each community area, compute average CTA ridership across all
    stations in that area for a given *year* and *day_type*.

    day_type: 'W' = Weekday, 'A' = Saturday, 'U' = Sunday/Holiday
    Note: rides in rail_ridership are monthly averages per day type,
          so we use AVG (not SUM) for a meaningful comparison.

    Tables: rail_ridership, cta_rail_stations, community_areas
    """
    sql = """
        SELECT ca.community_id,
               ca.name                           AS community_area,
               COUNT(DISTINCT rs.station_id)     AS num_stations,
               ROUND(AVG(rr.rides), 0)           AS avg_daily_rides
        FROM   rail_ridership rr
        JOIN   cta_rail_stations rs ON rs.station_id = rr.station_id
        JOIN   community_areas ca  ON ca.community_id = rs.community_id
        WHERE  rr.year = %s
          AND  rr.day_type = %s
        GROUP BY ca.community_id, ca.name
        ORDER BY avg_daily_rides DESC
    """
    return pd.read_sql(sql, conn, params=(year, day_type))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 5 — High Demand vs Service Efficiency
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_high_demand_efficient(conn, year: int = 2024, max_avg_days: int = 30):
    """
    Find community areas with a high number of 311 service requests
    (above city-wide average) but fast average response times
    (<= *max_avg_days* days) in a given *year*.

    Tables: service_requests, community_areas
    """
    sql = """
        WITH area_stats AS (
            SELECT community_id,
                   COUNT(*)                                        AS total_requests,
                   ROUND(AVG(DATEDIFF(closed_date, created_date)), 1) AS avg_response_days
            FROM   service_requests
            WHERE  year = %s
              AND  closed_date IS NOT NULL
            GROUP BY community_id
        )
        SELECT ca.community_id,
               ca.name               AS community_area,
               s.total_requests,
               s.avg_response_days
        FROM   area_stats s
        JOIN   community_areas ca ON ca.community_id = s.community_id
        WHERE  s.total_requests > (SELECT AVG(total_requests) FROM area_stats)
          AND  s.avg_response_days <= %s
        ORDER BY s.avg_response_days ASC
    """
    return pd.read_sql(sql, conn, params=(year, max_avg_days))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 6 — Most Accessible Neighborhoods (Transit Density)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_most_accessible(conn, top_n: int = 15):
    """
    Rank community areas by transit density = number of CTA rail stations
    per square mile.  Return the top *top_n* areas.

    Tables: cta_rail_stations, community_areas
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

def query_crime_near_housing(conn, year: int = 2024, min_housing_units: int = 5):
    """
    Find community areas where both total crime counts are above the
    city-wide average AND affordable housing units >= *min_housing_units*
    for a given *year*.

    Tables: crime_aggregations, housing_units, community_areas
    """
    sql = """
        WITH area_crime AS (
            SELECT community_id,
                   SUM(crime_count) AS total_crimes
            FROM   crime_aggregations
            WHERE  year = %s
            GROUP BY community_id
        ),
        area_housing AS (
            SELECT community_id,
                   COUNT(*)    AS num_properties,
                   SUM(units)  AS total_units
            FROM   housing_units
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
    return pd.read_sql(sql, conn, params=(year, min_housing_units))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 8 — Transit Stop Popularity
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_transit_popularity(conn, top_n: int = 10, year: int = 2024):
    """
    Identify the top *top_n* transit stops with the highest average
    ridership in a given *year*, along with their community areas.

    Tables: rail_ridership, cta_rail_stations, community_areas
    """
    sql = """
        SELECT rs.station_id,
               rs.station_name,
               ca.name                     AS community_area,
               ROUND(AVG(rr.rides), 0)     AS avg_daily_rides
        FROM   rail_ridership rr
        JOIN   cta_rail_stations rs ON rs.station_id = rr.station_id
        LEFT JOIN community_areas ca ON ca.community_id = rs.community_id
        WHERE  rr.year = %s
        GROUP BY rs.station_id, rs.station_name, ca.name
        ORDER BY avg_daily_rides DESC
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(year, top_n))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 9 — Service Request Delays
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_service_delays(conn, year: int = 2024, top_n: int = 15):
    """
    Find the community areas with the longest average 311 response time
    in a given *year*.  Return the top *top_n* slowest areas.

    Tables: service_requests, community_areas
    """
    sql = """
        SELECT ca.community_id,
               ca.name                                                AS community_area,
               COUNT(*)                                               AS total_requests,
               ROUND(AVG(DATEDIFF(sr.closed_date, sr.created_date)), 1) AS avg_response_days
        FROM   service_requests sr
        JOIN   community_areas ca ON ca.community_id = sr.community_id
        WHERE  sr.year = %s
          AND  sr.closed_date IS NOT NULL
        GROUP BY ca.community_id, ca.name
        ORDER BY avg_response_days DESC
        LIMIT %s
    """
    return pd.read_sql(sql, conn, params=(year, top_n))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 10 — Demographics vs Crime
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_demographics_vs_crime(conn):
    """
    Show median household income alongside crime rate for each community
    area to let users analyze the relationship between the two.

    Tables: census_profiles, neighborhood_profiles, community_areas
    """
    sql = """
        SELECT ca.community_id,
               ca.name                         AS community_area,
               cp.total_population             AS population,
               cp.median_household_income      AS median_income,
               np.crime_rate_per_1000          AS crime_rate
        FROM   census_profiles cp
        JOIN   neighborhood_profiles np ON np.community_id = cp.community_id
        JOIN   community_areas ca      ON ca.community_id = cp.community_id
        WHERE  cp.median_household_income IS NOT NULL
          AND  np.crime_rate_per_1000     IS NOT NULL
        ORDER BY cp.median_household_income DESC
    """
    return pd.read_sql(sql, conn)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 11 — Neighborhood Profile Ranking (Composite Score)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_neighborhood_ranking(conn, top_n: int = 20):
    """
    Rank community areas with a composite livability score that combines:
      • crime rate         (lower  is better → inverted)
      • affordable units   (higher is better)
      • transit density    (higher is better)
      • avg 311 response   (lower  is better → inverted)

    Each dimension is min-max normalized to [0,1], then averaged.

    Tables: neighborhood_profiles, community_areas, cta_rail_stations,
            service_requests, census_profiles
    """
    sql = """
        WITH transit AS (
            SELECT rs.community_id,
                   COUNT(*) / ca.area_sq_miles AS transit_density
            FROM   cta_rail_stations rs
            JOIN   community_areas ca ON ca.community_id = rs.community_id
            WHERE  rs.community_id IS NOT NULL
            GROUP BY rs.community_id, ca.area_sq_miles
        ),
        response AS (
            SELECT community_id,
                   AVG(DATEDIFF(closed_date, created_date)) AS avg_resp
            FROM   service_requests
            WHERE  closed_date IS NOT NULL AND year = 2024
            GROUP BY community_id
        ),
        raw AS (
            SELECT ca.community_id,
                   ca.name,
                   np.crime_rate_per_1000,
                   np.affordable_unit_count,
                   COALESCE(t.transit_density, 0)  AS transit_density,
                   COALESCE(r.avg_resp, 999)       AS avg_resp
            FROM   community_areas ca
            JOIN   neighborhood_profiles np ON np.community_id = ca.community_id
            LEFT JOIN transit t              ON t.community_id  = ca.community_id
            LEFT JOIN response r             ON r.community_id  = ca.community_id
            WHERE  np.crime_rate_per_1000 IS NOT NULL
        ),
        bounds AS (
            SELECT MIN(crime_rate_per_1000)    AS cr_min,  MAX(crime_rate_per_1000)    AS cr_max,
                   MIN(affordable_unit_count)  AS au_min,  MAX(affordable_unit_count)  AS au_max,
                   MIN(transit_density)         AS td_min,  MAX(transit_density)         AS td_max,
                   MIN(avg_resp)                AS ar_min,  MAX(avg_resp)                AS ar_max
            FROM raw
        )
        SELECT r.community_id,
               r.name                           AS community_area,
               r.crime_rate_per_1000            AS crime_rate,
               r.affordable_unit_count          AS affordable_units,
               ROUND(r.transit_density, 2)      AS transit_density,
               ROUND(r.avg_resp, 1)             AS avg_response_days,
               ROUND(
                   (
                     (1 - (r.crime_rate_per_1000   - b.cr_min) / NULLIF(b.cr_max - b.cr_min, 0))
                   + (    (r.affordable_unit_count - b.au_min) / NULLIF(b.au_max - b.au_min, 0))
                   + (    (r.transit_density        - b.td_min) / NULLIF(b.td_max - b.td_min, 0))
                   + (1 - (r.avg_resp               - b.ar_min) / NULLIF(b.ar_max - b.ar_min, 0))
                   ) / 4
               , 3)                             AS livability_score
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
    For each community area, count the total number of affordable housing
    units and properties.

    Tables: housing_units, community_areas
    """
    sql = """
        SELECT ca.community_id,
               ca.name               AS community_area,
               COUNT(hu.unit_id)     AS num_properties,
               COALESCE(SUM(hu.units), 0) AS total_units
        FROM   community_areas ca
        LEFT JOIN housing_units hu ON hu.community_id = ca.community_id
        GROUP BY ca.community_id, ca.name
        ORDER BY total_units DESC
    """
    return pd.read_sql(sql, conn)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Query 14 — Peak Transit Days
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def query_peak_transit_days(conn, year: int = 2024):
    """
    For each community area, find which day type (W=weekday, A=Saturday,
    U=Sunday/Holiday) has the highest average ridership in a given *year*.

    Tables: rail_ridership, cta_rail_stations, community_areas
    """
    sql = """
        WITH daily AS (
            SELECT ca.community_id,
                   ca.name                     AS community_area,
                   rr.day_type,
                   ROUND(AVG(rr.rides), 0)     AS avg_rides
            FROM   rail_ridership rr
            JOIN   cta_rail_stations rs ON rs.station_id  = rr.station_id
            JOIN   community_areas ca  ON ca.community_id = rs.community_id
            WHERE  rr.year = %s
            GROUP BY ca.community_id, ca.name, rr.day_type
        ),
        ranked AS (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY community_id
                       ORDER BY avg_rides DESC
                   ) AS rn
            FROM daily
        )
        SELECT community_id,
               community_area,
               CASE day_type
                   WHEN 'W' THEN 'Weekday'
                   WHEN 'A' THEN 'Saturday'
                   WHEN 'U' THEN 'Sunday / Holiday'
               END                AS peak_day_type,
               avg_rides          AS avg_rides_on_peak_day
        FROM   ranked
        WHERE  rn = 1
        ORDER BY avg_rides_on_peak_day DESC
    """
    return pd.read_sql(sql, conn, params=(year,))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Insert helper — add a new housing unit (Step 3 requirement)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def insert_housing_unit(
    conn,
    unit_id: int,
    community_id: int,
    property_name: str,
    property_type: str,
    units: int,
    address: str,
    management_company: str = None,
):
    """
    Insert a new affordable housing unit record.
    Returns True on success, raises on failure.

    Table: housing_units
    """
    sql = """
        INSERT INTO housing_units
            (unit_id, community_id, management_company,
             property_name, property_type, units, address)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    cursor = conn.cursor()
    cursor.execute(sql, (
        unit_id, community_id, management_company,
        property_name, property_type, units, address,
    ))
    conn.commit()
    cursor.close()
    return True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Utility — list community areas (for dropdowns / validation)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_community_areas(conn):
    """Return all 77 community areas as a DataFrame (for dropdowns)."""
    sql = "SELECT community_id, name FROM community_areas ORDER BY name"
    return pd.read_sql(sql, conn)


