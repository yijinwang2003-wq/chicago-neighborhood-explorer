USE chicago_neighborhood_explorer;

CREATE TABLE community_areas (
    community_id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    centroid_lat DECIMAL(10, 7),
    centroid_lng DECIMAL(10, 7),
    area_sq_miles DECIMAL(10, 6) NOT NULL,
    CHECK (community_id BETWEEN 1 AND 77),
    CHECK (area_sq_miles > 0),
    CHECK (centroid_lat IS NULL OR centroid_lat BETWEEN -90 AND 90),
    CHECK (centroid_lng IS NULL OR centroid_lng BETWEEN -180 AND 180)
);

CREATE TABLE wards (
    ward_id INT PRIMARY KEY,
    boundary_version VARCHAR(30) NOT NULL DEFAULT '2023-present',
    CHECK (ward_id BETWEEN 1 AND 50)
);

CREATE TABLE community_area_ward_overlap (
    community_id INT NOT NULL,
    ward_id INT NOT NULL,
    overlap_sq_miles DECIMAL(10, 6) NOT NULL,
    pct_of_community_area DECIMAL(6, 3) NOT NULL,
    pct_of_ward DECIMAL(6, 3) NOT NULL,
    PRIMARY KEY (community_id, ward_id),
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id),
    FOREIGN KEY (ward_id) REFERENCES wards(ward_id),
    CHECK (overlap_sq_miles > 0),
    CHECK (pct_of_community_area > 0 AND pct_of_community_area <= 100),
    CHECK (pct_of_ward > 0 AND pct_of_ward <= 100)
);

CREATE TABLE census_profiles (
    community_id INT PRIMARY KEY,
    cmap_release_year SMALLINT NOT NULL,
    acs_estimate_period VARCHAR(20) NOT NULL,
    population INT NOT NULL,
    median_household_income DECIMAL(12, 2),
    median_age DECIMAL(5, 2),
    unemployment_rate DECIMAL(6, 3),
    pct_bachelors DECIMAL(6, 3),
    housing_cost_burden_30plus_pct DECIMAL(6, 3),
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id),
    CHECK (population >= 0),
    CHECK (median_age IS NULL OR median_age >= 0),
    CHECK (unemployment_rate IS NULL OR unemployment_rate BETWEEN 0 AND 100),
    CHECK (pct_bachelors IS NULL OR pct_bachelors BETWEEN 0 AND 100),
    CHECK (
        housing_cost_burden_30plus_pct IS NULL
        OR housing_cost_burden_30plus_pct BETWEEN 0 AND 100
    )
);

CREATE TABLE management_companies (
    company_id INT PRIMARY KEY AUTO_INCREMENT,
    company_name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE housing_developments (
    development_id INT PRIMARY KEY AUTO_INCREMENT,
    source_record_key CHAR(64) NOT NULL UNIQUE,
    property_name VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL,
    raw_property_type VARCHAR(100),
    reported_unit_count INT,
    contact_phone VARCHAR(30),
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    community_id INT NOT NULL,
    company_id INT,
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id),
    FOREIGN KEY (company_id) REFERENCES management_companies(company_id),
    CHECK (reported_unit_count IS NULL OR reported_unit_count >= 0),
    CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180)
);

CREATE TABLE crime_records (
    crime_id BIGINT PRIMARY KEY,
    case_number VARCHAR(30),
    crime_date DATETIME NOT NULL,
    primary_type VARCHAR(100),
    description VARCHAR(255),
    location_description VARCHAR(255),
    arrest BOOLEAN,
    domestic BOOLEAN,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    community_id INT NOT NULL,
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id),
    CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180)
);

CREATE TABLE cta_rail_stations (
    station_id INT PRIMARY KEY,
    station_name VARCHAR(255) NOT NULL,
    ada_accessible BOOLEAN,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    community_id INT,
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id),
    CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180)
);

CREATE TABLE cta_lines (
    line_id INT PRIMARY KEY AUTO_INCREMENT,
    line_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE serves (
    station_id INT NOT NULL,
    line_id INT NOT NULL,
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
    FOREIGN KEY (station_id) REFERENCES cta_rail_stations(station_id),
    CHECK (month_total IS NULL OR month_total >= 0)
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
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id),
    CHECK (closed_date IS NULL OR closed_date >= created_date),
    CHECK (record_source = 'GUI_INPUT' OR source_sr_number IS NOT NULL)
);
