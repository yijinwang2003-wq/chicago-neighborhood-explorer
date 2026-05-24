USE chicago_neighborhood_explorer;

CREATE OR REPLACE VIEW vw_CrimeAggregation AS
SELECT
    community_id,
    YEAR(crime_date) AS crime_year,
    MONTH(crime_date) AS crime_month,
    primary_type AS crime_type,
    COUNT(*) AS crime_count
FROM CrimeRecord
GROUP BY community_id, YEAR(crime_date), MONTH(crime_date), primary_type;

CREATE OR REPLACE VIEW vw_NeighborhoodProfile AS
SELECT
    ca.community_id,
    ca.name AS community_name,
    cp.cmap_release_year,
    cp.acs_estimate_period,
    cp.population,
    cp.median_income,
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
FROM CommunityArea ca
LEFT JOIN CensusProfile cp ON ca.community_id = cp.community_id
LEFT JOIN (
    SELECT community_id, COUNT(*) AS crime_incidents_2025
    FROM CrimeRecord
    WHERE crime_date >= '2025-01-01' AND crime_date < '2026-01-01'
    GROUP BY community_id
) cr ON ca.community_id = cr.community_id
LEFT JOIN (
    SELECT
        community_id,
        SUM(COALESCE(reported_unit_count, 0))
          AS reported_city_supported_units_snapshot
    FROM HousingDevelopment
    GROUP BY community_id
) h ON ca.community_id = h.community_id
LEFT JOIN (
    SELECT community_id, COUNT(*) AS rail_station_count_snapshot
    FROM CTARailStation
    GROUP BY community_id
) st ON ca.community_id = st.community_id
LEFT JOIN (
    SELECT s.community_id, SUM(r.month_total) AS rail_entries_2025
    FROM RailRidershipMonthly r
    JOIN CTARailStation s ON r.station_id = s.station_id
    WHERE r.month_beginning >= '2025-01-01'
      AND r.month_beginning < '2026-01-01'
    GROUP BY s.community_id
) rr ON ca.community_id = rr.community_id
LEFT JOIN (
    SELECT
        community_id,
        ROUND(AVG(TIMESTAMPDIFF(MINUTE, created_date, closed_date)) / 60.0, 2)
          AS avg_closed_311_response_hours_2025
    FROM ServiceRequest
    WHERE record_source = 'OPEN_DATA'
      AND created_date >= '2025-01-01'
      AND created_date < '2026-01-01'
      AND closed_date IS NOT NULL
      AND closed_date >= created_date
    GROUP BY community_id
) sr ON ca.community_id = sr.community_id;
