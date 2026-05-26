USE chicago_neighborhood;

CREATE OR REPLACE VIEW vw_crime_aggregation AS
SELECT
    community_id,
    YEAR(date) AS crime_year,
    MONTH(date) AS crime_month,
    primary_type AS crime_type,
    COUNT(*) AS crime_count
FROM crime_records
GROUP BY community_id, YEAR(date), MONTH(date), primary_type;

CREATE OR REPLACE VIEW vw_neighborhood_profile AS
SELECT
    ca.community_id,
    ca.name AS community_name,
    cp.cmap_release_year,
    cp.acs_estimate_period,
    cp.population,
    cp.median_household_income,
    cp.unemployment_rate,
    cp.pct_bachelors,
    cp.housing_cost_burden_30plus_pct,
    COALESCE(cr.crime_incidents_2025, 0) AS crime_incidents_2025,
    ROUND(
        COALESCE(cr.crime_incidents_2025, 0) * 1000.0 / NULLIF(cp.population, 0),
        2
    ) AS crime_incidents_per_1000_population_estimate_2025,
    COALESCE(h.reported_city_supported_units_snapshot, 0)
        AS reported_city_supported_units_snapshot,
    COALESCE(st.rail_station_count_snapshot, 0)
        AS rail_station_count_snapshot,
    ROUND(
        COALESCE(st.rail_station_count_snapshot, 0) / NULLIF(ca.area_sq_miles, 0),
        2
    ) AS rail_station_density_snapshot,
    COALESCE(rr.rail_entries_2025, 0) AS rail_entries_2025,
    sr.avg_closed_311_response_hours_2025
FROM community_areas ca
LEFT JOIN census_profiles cp
    ON ca.community_id = cp.community_id
LEFT JOIN (
    SELECT community_id, COUNT(*) AS crime_incidents_2025
    FROM crime_records
    WHERE date >= '2025-01-01'
      AND date < '2026-01-01'
    GROUP BY community_id
) cr
    ON ca.community_id = cr.community_id
LEFT JOIN (
    SELECT
        community_id,
        SUM(COALESCE(reported_unit_count, 0))
            AS reported_city_supported_units_snapshot
    FROM housing_developments
    GROUP BY community_id
) h
    ON ca.community_id = h.community_id
LEFT JOIN (
    SELECT community_id, COUNT(*) AS rail_station_count_snapshot
    FROM cta_rail_stations
    WHERE community_id IS NOT NULL
    GROUP BY community_id
) st
    ON ca.community_id = st.community_id
LEFT JOIN (
    SELECT s.community_id, SUM(r.month_total) AS rail_entries_2025
    FROM rail_ridership_monthly r
    JOIN cta_rail_stations s
        ON r.station_id = s.station_id
    WHERE s.community_id IS NOT NULL
      AND r.month_beginning >= '2025-01-01'
      AND r.month_beginning < '2026-01-01'
    GROUP BY s.community_id
) rr
    ON ca.community_id = rr.community_id
LEFT JOIN (
    SELECT
        community_id,
        ROUND(AVG(TIMESTAMPDIFF(MINUTE, created_date, closed_date)) / 60.0, 2)
            AS avg_closed_311_response_hours_2025
    FROM service_requests
    WHERE record_source = 'OPEN_DATA'
      AND created_date >= '2025-01-01'
      AND created_date < '2026-01-01'
      AND closed_date IS NOT NULL
      AND closed_date >= created_date
    GROUP BY community_id
) sr
    ON ca.community_id = sr.community_id;

CREATE OR REPLACE VIEW vw_ward_community_profile AS
SELECT
    w.ward_id,
    ca.community_id,
    ca.name AS community_name,
    o.overlap_sq_miles,
    o.pct_of_ward,
    o.pct_of_community_area,
    p.crime_incidents_per_1000_population_estimate_2025,
    p.housing_cost_burden_30plus_pct,
    p.avg_closed_311_response_hours_2025
FROM wards w
JOIN community_area_ward_overlap o
    ON w.ward_id = o.ward_id
JOIN community_areas ca
    ON o.community_id = ca.community_id
JOIN vw_neighborhood_profile p
    ON ca.community_id = p.community_id;
