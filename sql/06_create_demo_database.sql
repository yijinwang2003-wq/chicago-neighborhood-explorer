-- ============================================================
-- Chicago Neighborhood Analytics Platform - Railway Demo Schema
-- ============================================================
-- This schema is for the lightweight Railway demo database.
-- It is built from the processed CSV files in db-data/chicago_neighborhood_data/
-- and is intentionally smaller than the full local benchmark database.
--
-- The import script is responsible for creating the database, loading the CSVs,
-- and populating neighborhood_profile_snapshot.
-- ============================================================

CREATE TABLE community_areas (
    community_id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    centroid_lat DECIMAL(10, 7),
    centroid_lng DECIMAL(10, 7),
    area_sq_miles DECIMAL(10, 6) NOT NULL
);

CREATE TABLE census_profiles (
    community_id INT PRIMARY KEY,
    total_population INT,
    median_household_income DECIMAL(12, 2),
    median_rent DECIMAL(12, 2),
    transit_share_pct DECIMAL(6, 3),
    pop_density_per_acre DECIMAL(10, 2),
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id)
);

CREATE TABLE neighborhood_profiles (
    community_id INT PRIMARY KEY,
    total_population INT,
    avg_rent DECIMAL(10, 2),
    crime_rate_per_1000 DECIMAL(10, 2),
    service_request_count_2024 INT,
    transit_ridership_monthly_avg DECIMAL(12, 0),
    affordable_unit_count INT NOT NULL DEFAULT 0,
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id)
);

CREATE TABLE wards (
    ward_id INT PRIMARY KEY,
    boundary_version VARCHAR(30) NOT NULL DEFAULT '2023-present'
);

CREATE TABLE community_area_ward_overlap (
    community_id INT NOT NULL,
    ward_id INT NOT NULL,
    overlap_sq_miles DECIMAL(10, 6) NOT NULL,
    pct_of_community_area DECIMAL(6, 3),
    pct_of_ward DECIMAL(6, 3),
    PRIMARY KEY (community_id, ward_id),
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id),
    FOREIGN KEY (ward_id) REFERENCES wards(ward_id)
);

CREATE TABLE management_companies (
    management_company VARCHAR(255) PRIMARY KEY,
    phone_number VARCHAR(20)
);

CREATE TABLE housing_developments (
    development_id INT PRIMARY KEY,
    source_record_key CHAR(64) NOT NULL UNIQUE,
    property_name VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL,
    raw_property_type VARCHAR(100),
    reported_unit_count INT,
    contact_phone VARCHAR(30),
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    community_id INT NOT NULL,
    management_company VARCHAR(255),
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id),
    FOREIGN KEY (management_company) REFERENCES management_companies(management_company)
);

CREATE TABLE cta_lines (
    line_id VARCHAR(20) PRIMARY KEY,
    line_name VARCHAR(50) NOT NULL
);

CREATE TABLE cta_rail_stations (
    station_id INT PRIMARY KEY,
    station_name VARCHAR(255) NOT NULL,
    ada_accessible BOOLEAN,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    community_id INT,
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id)
);

CREATE TABLE serves (
    station_id INT NOT NULL,
    line_id VARCHAR(20) NOT NULL,
    PRIMARY KEY (station_id, line_id),
    FOREIGN KEY (station_id) REFERENCES cta_rail_stations(station_id),
    FOREIGN KEY (line_id) REFERENCES cta_lines(line_id)
);

CREATE TABLE rail_ridership_monthly (
    station_id INT NOT NULL,
    month_beginning DATE NOT NULL,
    avg_weekday_rides DECIMAL(12, 1),
    avg_saturday_rides DECIMAL(12, 1),
    avg_sunday_holiday_rides DECIMAL(12, 1),
    month_total INT,
    PRIMARY KEY (station_id, month_beginning),
    FOREIGN KEY (station_id) REFERENCES cta_rail_stations(station_id)
);

CREATE TABLE crime_aggregations (
    community_id INT NOT NULL,
    year SMALLINT NOT NULL,
    month TINYINT NOT NULL,
    primary_type VARCHAR(100) NOT NULL,
    crime_count INT NOT NULL DEFAULT 0,
    PRIMARY KEY (community_id, year, month, primary_type),
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id)
);

CREATE TABLE crime_records (
    crime_id BIGINT PRIMARY KEY,
    case_number VARCHAR(50),
    crime_date DATETIME NOT NULL,
    primary_type VARCHAR(100),
    description VARCHAR(255),
    location_description VARCHAR(255),
    arrest BOOLEAN,
    domestic BOOLEAN,
    community_id INT NOT NULL,
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id),
    INDEX idx_crime_community_date (community_id, crime_date),
    INDEX idx_crime_type_date (primary_type, crime_date)
);

CREATE TABLE service_requests (
    service_request_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    source_sr_number VARCHAR(50) UNIQUE,
    request_type VARCHAR(255) NOT NULL,
    created_date DATETIME NOT NULL,
    closed_date DATETIME,
    status VARCHAR(50),
    street_address VARCHAR(255),
    zip_code VARCHAR(20),
    community_id INT NOT NULL,
    record_source ENUM('OPEN_DATA', 'GUI_INPUT') NOT NULL DEFAULT 'OPEN_DATA',
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id)
);

CREATE TABLE neighborhood_profile_snapshot (
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

CREATE OR REPLACE VIEW vw_crime_aggregation AS
SELECT
    community_id,
    year AS crime_year,
    month AS crime_month,
    primary_type AS crime_type,
    SUM(crime_count) AS crime_count
FROM crime_aggregations
GROUP BY community_id, year, month, primary_type;

CREATE OR REPLACE VIEW vw_neighborhood_profile AS
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
    avg_closed_311_response_hours_2025
FROM neighborhood_profile_snapshot;

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
    ON o.ward_id = w.ward_id
JOIN community_areas ca
    ON ca.community_id = o.community_id
JOIN neighborhood_profile_snapshot p
    ON p.community_id = ca.community_id;
