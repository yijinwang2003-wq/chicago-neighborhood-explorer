CREATE TABLE CommunityArea (
    community_id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    area_sq_miles DECIMAL(10, 6) NOT NULL,
    CHECK (community_id BETWEEN 1 AND 77),
    CHECK (area_sq_miles > 0)
);

CREATE TABLE CensusProfile (
    community_id INT PRIMARY KEY,
    cmap_release_year SMALLINT NOT NULL,
    acs_estimate_period VARCHAR(20) NOT NULL,
    population INT NOT NULL,
    median_income DECIMAL(12, 2),
    median_age DECIMAL(5, 2),
    unemployment_rate DECIMAL(6, 3),
    pct_bachelors DECIMAL(6, 3),
    housing_cost_burden_30plus_pct DECIMAL(6, 3),
    FOREIGN KEY (community_id) REFERENCES CommunityArea(community_id),
    CHECK (population >= 0),
    CHECK (
        housing_cost_burden_30plus_pct IS NULL
        OR housing_cost_burden_30plus_pct BETWEEN 0 AND 100
    )
);

CREATE TABLE ManagementCompany (
    company_id INT PRIMARY KEY AUTO_INCREMENT,
    company_name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE HousingDevelopment (
    development_id INT PRIMARY KEY AUTO_INCREMENT,
    source_record_key CHAR(64) NOT NULL UNIQUE,
    property_name VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL,
    property_type VARCHAR(100),
    reported_unit_count INT,
    contact_phone VARCHAR(30),
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    community_id INT NOT NULL,
    company_id INT,
    FOREIGN KEY (community_id) REFERENCES CommunityArea(community_id),
    FOREIGN KEY (company_id) REFERENCES ManagementCompany(company_id),
    CHECK (reported_unit_count IS NULL OR reported_unit_count >= 0)
);

CREATE TABLE CrimeRecord (
    incident_id BIGINT PRIMARY KEY,
    crime_date DATETIME NOT NULL,
    primary_type VARCHAR(100),
    description VARCHAR(255),
    location_description VARCHAR(255),
    arrest BOOLEAN,
    domestic BOOLEAN,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    community_id INT NOT NULL,
    FOREIGN KEY (community_id) REFERENCES CommunityArea(community_id)
);

CREATE TABLE CTARailStation (
    station_id INT PRIMARY KEY,
    station_name VARCHAR(255) NOT NULL,
    ada_accessible BOOLEAN,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    community_id INT NOT NULL,
    FOREIGN KEY (community_id) REFERENCES CommunityArea(community_id)
);

CREATE TABLE CTALine (
    line_id INT PRIMARY KEY AUTO_INCREMENT,
    line_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE Serves (
    station_id INT,
    line_id INT,
    PRIMARY KEY (station_id, line_id),
    FOREIGN KEY (station_id) REFERENCES CTARailStation(station_id),
    FOREIGN KEY (line_id) REFERENCES CTALine(line_id)
);

CREATE TABLE RailRidershipMonthly (
    station_id INT,
    month_beginning DATE,
    avg_weekday_rides DECIMAL(12, 1),
    avg_saturday_rides DECIMAL(12, 1),
    avg_sunday_holiday_rides DECIMAL(12, 1),
    month_total INT,
    PRIMARY KEY (station_id, month_beginning),
    FOREIGN KEY (station_id) REFERENCES CTARailStation(station_id),
    CHECK (month_total IS NULL OR month_total >= 0)
);

CREATE TABLE ServiceRequest (
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
    FOREIGN KEY (community_id) REFERENCES CommunityArea(community_id),
    CHECK (closed_date IS NULL OR closed_date >= created_date),
    CHECK (record_source = 'GUI_INPUT' OR source_sr_number IS NOT NULL)
);

CREATE TABLE Near_Stop (
    development_id INT,
    station_id INT,
    distance_meters DECIMAL(10, 2) NOT NULL,
    PRIMARY KEY (development_id, station_id),
    FOREIGN KEY (development_id) REFERENCES HousingDevelopment(development_id),
    FOREIGN KEY (station_id) REFERENCES CTARailStation(station_id),
    CHECK (distance_meters BETWEEN 0 AND 1000)
);
