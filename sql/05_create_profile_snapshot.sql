USE chicago_neighborhood;

CREATE TABLE IF NOT EXISTS neighborhood_profile_snapshot (
    community_id INT NOT NULL,
    community_name VARCHAR(100) NOT NULL,
    cmap_release_year SMALLINT,
    acs_estimate_period VARCHAR(20),
    population INT,
    median_household_income DECIMAL(12, 2),
    unemployment_rate DECIMAL(6, 3),
    pct_bachelors DECIMAL(6, 3),
    housing_cost_burden_30plus_pct DECIMAL(6, 3),
    crime_incidents_2025 BIGINT NOT NULL DEFAULT 0,
    crime_incidents_per_1000_population_estimate_2025 DECIMAL(12, 2),
    reported_city_supported_units_snapshot DECIMAL(18, 2) NOT NULL DEFAULT 0,
    rail_station_count_snapshot BIGINT NOT NULL DEFAULT 0,
    rail_station_density_snapshot DECIMAL(12, 2),
    rail_entries_2025 BIGINT NOT NULL DEFAULT 0,
    avg_closed_311_response_hours_2025 DECIMAL(12, 2),
    refreshed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (community_id),
    INDEX idx_profile_snapshot_name (community_name)
);

DROP PROCEDURE IF EXISTS refresh_neighborhood_profile_snapshot;

DELIMITER //

CREATE PROCEDURE refresh_neighborhood_profile_snapshot()
BEGIN
    TRUNCATE TABLE neighborhood_profile_snapshot;

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
        CURRENT_TIMESTAMP
    FROM vw_neighborhood_profile;
END //

DELIMITER ;

CALL refresh_neighborhood_profile_snapshot();
