-- ============================================================
-- Chicago Neighborhood Explorer — MySQL Data Load Script
-- MPCS 53001 Databases — Final Project Step 3
-- ============================================================
-- Prerequisites:
--   1. Run schema.sql to create all tables.
--   2. Download chicago_neighborhood_data.zip from the shared
--      drive, extract it, and note the folder path.
--
-- How to run:
--   mysql -u root -p --local-infile=1 chicago_neighborhood < load_data.sql
--
-- If LOAD DATA LOCAL INFILE is blocked by your MySQL server:
--   SET GLOBAL local_infile = 1;   -- run once as root in MySQL
--
-- ⚠️  BEFORE RUNNING: replace every occurrence of
--       /REPLACE_WITH_YOUR_DATA_PATH
--     with the folder where you extracted chicago_neighborhood_data.zip.
--
--     Mac example:
--       /Users/yourname/Downloads/chicago_neighborhood_data
--     Windows example:
--       C:/Users/yourname/Downloads/chicago_neighborhood_data
--
-- Data files expected (all in one flat folder after extracting zip):
--   community_areas.csv, census_profiles.csv, cta_rail_stations.csv,
--   cta_lines.csv, serves.csv, crime_records.csv, crime_aggregations.csv,
--   management_companies.csv, housing_units.csv, rail_ridership.csv,
--   service_requests.csv, neighborhood_profiles.csv, wards.csv,
--   community_area_ward_overlap.csv
-- ============================================================

USE chicago_neighborhood;

-- Performance settings for bulk load (restore after if needed)
SET FOREIGN_KEY_CHECKS = 0;
SET UNIQUE_CHECKS     = 0;
SET autocommit        = 0;

-- ── (1) community_areas ───────────────────────────────────────
LOAD DATA LOCAL INFILE
    '/REPLACE_WITH_YOUR_DATA_PATH/community_areas.csv'
INTO TABLE community_areas
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES  TERMINATED BY '\n'
IGNORE 1 ROWS
(community_id, name, centroid_lat, centroid_lng, area_sq_miles);

-- ── (2) census_profiles ───────────────────────────────────────
LOAD DATA LOCAL INFILE
    '/REPLACE_WITH_YOUR_DATA_PATH/census_profiles.csv'
INTO TABLE census_profiles
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES  TERMINATED BY '\n'
IGNORE 1 ROWS
(@community_id, @total_population, @median_household_income, @median_rent, @transit_share_pct, @pop_density_per_acre)
SET
    community_id            = NULLIF(@community_id, ''),
    total_population        = NULLIF(@total_population, ''),
    median_household_income = NULLIF(@median_household_income, ''),
    median_rent             = NULLIF(@median_rent, ''),
    transit_share_pct       = NULLIF(@transit_share_pct, ''),
    pop_density_per_acre    = NULLIF(@pop_density_per_acre, '');

-- ── (3) cta_rail_stations ────────────────────────────────────
-- ada is pandas bool: 'True'/'False' — convert to 1/0
LOAD DATA LOCAL INFILE
    '/REPLACE_WITH_YOUR_DATA_PATH/cta_rail_stations.csv'
INTO TABLE cta_rail_stations
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES  TERMINATED BY '\n'
IGNORE 1 ROWS
(@station_id, @station_name, @community_id, @latitude, @longitude, @ada)
SET
    station_id   = @station_id,
    station_name = @station_name,
    community_id = NULLIF(@community_id, ''),
    latitude     = NULLIF(@latitude, ''),
    longitude    = NULLIF(@longitude, ''),
    ada          = IF(@ada = 'True', 1, 0);

-- ── (4) cta_lines ────────────────────────────────────────────
LOAD DATA LOCAL INFILE
    '/REPLACE_WITH_YOUR_DATA_PATH/cta_lines.csv'
INTO TABLE cta_lines
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES  TERMINATED BY '\n'
IGNORE 1 ROWS
(line_id, line_name);

-- ── (5) serves ───────────────────────────────────────────────
LOAD DATA LOCAL INFILE
    '/REPLACE_WITH_YOUR_DATA_PATH/serves.csv'
INTO TABLE serves
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES  TERMINATED BY '\n'
IGNORE 1 ROWS
(station_id, line_id);

-- ── (6) crime_records (~1.5M rows — takes ~2 min) ─────────────
-- arrest/domestic are Spark bools: 'true'/'false' — convert to 1/0
LOAD DATA LOCAL INFILE
    '/REPLACE_WITH_YOUR_DATA_PATH/crime_records.csv'
INTO TABLE crime_records
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES  TERMINATED BY '\n'
IGNORE 1 ROWS
(@crime_id, @case_number, @community_id, @date, @year, @month, @primary_type, @description, @location_description, @arrest, @domestic)
SET
    crime_id             = @crime_id,
    case_number          = NULLIF(@case_number, ''),
    community_id         = @community_id,
    date                 = @date,
    year                 = @year,
    month                = @month,
    primary_type         = @primary_type,
    description          = NULLIF(@description, ''),
    location_description = NULLIF(@location_description, ''),
    arrest               = IF(@arrest  = 'true', 1, 0),
    domestic             = IF(@domestic = 'true', 1, 0);

-- ── (7) crime_aggregations ───────────────────────────────────
LOAD DATA LOCAL INFILE
    '/REPLACE_WITH_YOUR_DATA_PATH/crime_aggregations.csv'
INTO TABLE crime_aggregations
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES  TERMINATED BY '\n'
IGNORE 1 ROWS
(community_id, year, month, primary_type, crime_count);

-- ── (8) management_companies ─────────────────────────────────
LOAD DATA LOCAL INFILE
    '/REPLACE_WITH_YOUR_DATA_PATH/management_companies.csv'
INTO TABLE management_companies
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES  TERMINATED BY '\n'
IGNORE 1 ROWS
(@management_company, @phone_number)
SET
    management_company = @management_company,
    phone_number       = NULLIF(@phone_number, '');

-- ── (9) housing_units ────────────────────────────────────────
LOAD DATA LOCAL INFILE
    '/REPLACE_WITH_YOUR_DATA_PATH/housing_units.csv'
INTO TABLE housing_units
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES  TERMINATED BY '\n'
IGNORE 1 ROWS
(@unit_id, @community_id, @management_company, @property_name, @property_type, @units, @address)
SET
    unit_id            = @unit_id,
    community_id       = NULLIF(@community_id, ''),
    management_company = NULLIF(@management_company, ''),
    property_name      = NULLIF(@property_name, ''),
    property_type      = NULLIF(@property_type, ''),
    units              = NULLIF(@units, ''),
    address            = NULLIF(@address, '');

-- ── (10) rail_ridership ──────────────────────────────────────
LOAD DATA LOCAL INFILE
    '/REPLACE_WITH_YOUR_DATA_PATH/rail_ridership.csv'
INTO TABLE rail_ridership
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES  TERMINATED BY '\n'
IGNORE 1 ROWS
(@station_id, @year, @month, @day_type, @rides)
SET
    station_id = @station_id,
    year       = @year,
    month      = @month,
    day_type   = @day_type,
    rides      = NULLIF(@rides, '');

-- ── (11) service_requests (~7.7M rows — takes ~10 min) ────────
LOAD DATA LOCAL INFILE
    '/REPLACE_WITH_YOUR_DATA_PATH/service_requests.csv'
INTO TABLE service_requests
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES  TERMINATED BY '\n'
IGNORE 1 ROWS
(@sr_number, @community_id, @created_date, @closed_date, @year, @month, @request_type, @status)
SET
    sr_number    = @sr_number,
    community_id = @community_id,
    created_date = @created_date,
    closed_date  = NULLIF(@closed_date, ''),
    year         = @year,
    month        = @month,
    request_type = NULLIF(@request_type, ''),
    status       = NULLIF(@status, '');

-- ── (12) neighborhood_profiles ───────────────────────────────
LOAD DATA LOCAL INFILE
    '/REPLACE_WITH_YOUR_DATA_PATH/neighborhood_profiles.csv'
INTO TABLE neighborhood_profiles
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES  TERMINATED BY '\n'
IGNORE 1 ROWS
(@community_id, @total_population, @avg_rent, @crime_rate_per_1000, @service_request_count_2024, @transit_ridership_monthly_avg, @affordable_unit_count)
SET
    community_id                  = @community_id,
    total_population              = NULLIF(@total_population, ''),
    avg_rent                      = NULLIF(@avg_rent, ''),
    crime_rate_per_1000           = NULLIF(@crime_rate_per_1000, ''),
    service_request_count_2024    = NULLIF(@service_request_count_2024, ''),
    transit_ridership_monthly_avg = NULLIF(@transit_ridership_monthly_avg, ''),
    affordable_unit_count         = @affordable_unit_count;

-- ── (13) wards ───────────────────────────────────────────────
LOAD DATA LOCAL INFILE
    '/REPLACE_WITH_YOUR_DATA_PATH/wards.csv'
INTO TABLE wards
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES  TERMINATED BY '\n'
IGNORE 1 ROWS
(ward_id, boundary_version);

-- ── (14) community_area_ward_overlap ─────────────────────────
LOAD DATA LOCAL INFILE
    '/REPLACE_WITH_YOUR_DATA_PATH/community_area_ward_overlap.csv'
INTO TABLE community_area_ward_overlap
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES  TERMINATED BY '\n'
IGNORE 1 ROWS
(@community_id, @ward_id, @overlap_sq_miles, @pct_of_community_area, @pct_of_ward)
SET
    community_id          = @community_id,
    ward_id               = @ward_id,
    overlap_sq_miles      = @overlap_sq_miles,
    pct_of_community_area = NULLIF(@pct_of_community_area, ''),
    pct_of_ward           = NULLIF(@pct_of_ward, '');

-- Commit and restore settings
COMMIT;
SET FOREIGN_KEY_CHECKS = 1;
SET UNIQUE_CHECKS     = 1;
SET autocommit        = 1;

-- ── Quick verification ────────────────────────────────────────
SELECT 'community_areas'            AS tbl, COUNT(*) AS row_count FROM community_areas        UNION ALL
SELECT 'census_profiles',                   COUNT(*)         FROM census_profiles             UNION ALL
SELECT 'cta_rail_stations',                 COUNT(*)         FROM cta_rail_stations           UNION ALL
SELECT 'cta_lines',                         COUNT(*)         FROM cta_lines                   UNION ALL
SELECT 'serves',                            COUNT(*)         FROM serves                      UNION ALL
SELECT 'crime_records',                     COUNT(*)         FROM crime_records               UNION ALL
SELECT 'crime_aggregations',                COUNT(*)         FROM crime_aggregations          UNION ALL
SELECT 'management_companies',              COUNT(*)         FROM management_companies        UNION ALL
SELECT 'housing_units',                     COUNT(*)         FROM housing_units               UNION ALL
SELECT 'rail_ridership',                    COUNT(*)         FROM rail_ridership              UNION ALL
SELECT 'service_requests',                  COUNT(*)         FROM service_requests            UNION ALL
SELECT 'neighborhood_profiles',             COUNT(*)         FROM neighborhood_profiles       UNION ALL
SELECT 'wards',                             COUNT(*)         FROM wards                       UNION ALL
SELECT 'community_area_ward_overlap',       COUNT(*)         FROM community_area_ward_overlap
ORDER BY tbl;
