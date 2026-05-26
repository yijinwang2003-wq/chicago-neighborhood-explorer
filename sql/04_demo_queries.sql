USE chicago_neighborhood_explorer;

-- Query 1: Compare neighborhood profiles.
SELECT
    community_name,
    crime_incidents_per_1000_population_estimate_2025 AS crime_rate,
    housing_cost_burden_30plus_pct AS cost_burden_pct,
    reported_city_supported_units_snapshot AS reported_units,
    rail_station_density_snapshot AS station_density,
    avg_closed_311_response_hours_2025 AS avg_311_hours
FROM vw_neighborhood_profile
ORDER BY crime_rate ASC, avg_311_hours ASC
LIMIT 10;

-- Query 2: View crime trends for a selected community and optional crime type.
SET @community_id = 25;
SET @crime_type = NULL;

SELECT crime_month, crime_type, crime_count
FROM vw_crime_aggregation
WHERE community_id = @community_id
  AND crime_year = 2025
  AND (@crime_type IS NULL OR crime_type = @crime_type)
ORDER BY crime_month, crime_type;

-- Query 3: View community areas overlapping a selected ward.
SET @ward_id = 27;

SELECT
    ward_id,
    community_name,
    ROUND(overlap_sq_miles, 4) AS overlap_sq_miles,
    ROUND(pct_of_ward, 2) AS pct_of_ward,
    ROUND(pct_of_community_area, 2) AS pct_of_community_area,
    crime_incidents_per_1000_population_estimate_2025 AS crime_rate,
    housing_cost_burden_30plus_pct AS cost_burden_pct,
    avg_closed_311_response_hours_2025 AS avg_311_hours
FROM vw_ward_community_profile
WHERE ward_id = @ward_id
ORDER BY pct_of_ward DESC, community_name;

-- Query 4: Find city-supported affordable housing near CTA rail stations.
SET @community_id = 25;
SET @max_distance_meters = 800;

WITH candidate_distances AS (
    SELECT
        h.property_name,
        ca.name AS community_name,
        s.station_id,
        s.station_name,
        ST_Distance_Sphere(
            POINT(h.longitude, h.latitude),
            POINT(s.longitude, s.latitude)
        ) AS distance_meters
    FROM housing_developments h
    JOIN community_areas ca
        ON h.community_id = ca.community_id
    CROSS JOIN cta_rail_stations s
    WHERE h.community_id = @community_id
      AND h.latitude IS NOT NULL
      AND h.longitude IS NOT NULL
      AND s.latitude IS NOT NULL
      AND s.longitude IS NOT NULL
)
SELECT
    cd.property_name,
    cd.community_name,
    cd.station_name,
    l.line_name,
    ROUND(cd.distance_meters, 1) AS distance_meters
FROM candidate_distances cd
LEFT JOIN serves sv
    ON cd.station_id = sv.station_id
LEFT JOIN cta_lines l
    ON sv.line_id = l.line_id
WHERE cd.distance_meters <= @max_distance_meters
ORDER BY cd.distance_meters, cd.property_name, l.line_name;

-- Query 5: Display neighborhoods with the highest CTA rail entries in 2025.
SELECT community_name, rail_entries_2025, rail_station_count_snapshot
FROM vw_neighborhood_profile
ORDER BY rail_entries_2025 DESC
LIMIT 10;

-- Query 6: Compare average closed 311 response time in 2025.
SELECT community_name, avg_closed_311_response_hours_2025
FROM vw_neighborhood_profile
WHERE avg_closed_311_response_hours_2025 IS NOT NULL
ORDER BY avg_closed_311_response_hours_2025 ASC
LIMIT 10;

-- Insert feature: add one local project service-request record.
INSERT INTO service_requests (
    source_sr_number,
    request_type,
    created_date,
    closed_date,
    status,
    street_address,
    zip_code,
    community_id,
    record_source
) VALUES (
    NULL,
    'Street Light Out',
    NOW(),
    NULL,
    'Open',
    '5801 S Ellis Ave',
    '60637',
    41,
    'GUI_INPUT'
);
