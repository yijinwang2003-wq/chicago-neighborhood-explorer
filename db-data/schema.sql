-- ============================================================
-- Chicago Neighborhood Explorer — MySQL Schema
-- MPCS 53001 Databases — Final Project Step 3
-- ============================================================
-- Run this file first to create all tables before loading data.
-- Order matters: child tables must follow the parent they reference.
--
-- Usage:
--   mysql -u root -p < schema.sql
--   OR paste into MySQL Workbench / DBeaver
-- ============================================================

CREATE DATABASE IF NOT EXISTS chicago_neighborhood;
USE chicago_neighborhood;

-- ── (1) community_areas ───────────────────────────────────────
-- 77 Chicago community areas. Primary geographic anchor for all other tables.
CREATE TABLE IF NOT EXISTS community_areas (
    community_id   INT           NOT NULL,
    name           VARCHAR(100)  NOT NULL,
    centroid_lat   DOUBLE,
    centroid_lng   DOUBLE,
    area_sq_miles  DECIMAL(10,4),
    PRIMARY KEY (community_id)
);

-- ── (2) census_profiles ───────────────────────────────────────
-- 2025 ACS demographic snapshot per community area (source: CCA_2025.csv).
-- 1:1 with community_areas — separated to satisfy 3NF (demographic attributes
-- belong to the census snapshot entity, not the geographic area entity).
CREATE TABLE IF NOT EXISTS census_profiles (
    community_id              INT           NOT NULL,
    total_population          INT,
    median_household_income   DECIMAL(10,2),
    median_rent               DECIMAL(10,2),
    transit_share_pct         DECIMAL(6,2),
    pop_density_per_acre      DECIMAL(10,2),
    PRIMARY KEY (community_id),
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id)
);

-- ── (3) cta_rail_stations ────────────────────────────────────
-- 144 CTA L rail stations (station level, not stop level).
-- community_id assigned via point-in-polygon spatial join; nullable for
-- stations on community area boundaries.
CREATE TABLE IF NOT EXISTS cta_rail_stations (
    station_id    INT          NOT NULL,
    station_name  VARCHAR(100) NOT NULL,
    community_id  INT,
    latitude      DOUBLE,
    longitude     DOUBLE,
    ada           TINYINT(1)   NOT NULL DEFAULT 0,
    PRIMARY KEY (station_id),
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id)
);

-- ── (4) cta_lines ────────────────────────────────────────────
-- 8 CTA rail lines.
CREATE TABLE IF NOT EXISTS cta_lines (
    line_id    VARCHAR(10)  NOT NULL,
    line_name  VARCHAR(50)  NOT NULL,
    PRIMARY KEY (line_id)
);

-- ── (5) serves ───────────────────────────────────────────────
-- M:N junction: which lines serve which stations.
-- First genuine M:N: a station serves multiple lines; a line serves many stations.
CREATE TABLE IF NOT EXISTS serves (
    station_id  INT         NOT NULL,
    line_id     VARCHAR(10) NOT NULL,
    PRIMARY KEY (station_id, line_id),
    FOREIGN KEY (station_id) REFERENCES cta_rail_stations(station_id),
    FOREIGN KEY (line_id)    REFERENCES cta_lines(line_id)
);

-- ── (6) crime_records ────────────────────────────────────────
-- Individual crime incidents 2020-2026 (~1.5M rows).
-- Satisfies the 500K+ record requirement independently.
CREATE TABLE IF NOT EXISTS crime_records (
    crime_id              BIGINT        NOT NULL,
    case_number           VARCHAR(20),
    community_id          INT           NOT NULL,
    date                  DATE          NOT NULL,
    year                  SMALLINT      NOT NULL,
    month                 TINYINT       NOT NULL,
    primary_type          VARCHAR(50)   NOT NULL,
    description           VARCHAR(100),
    location_description  VARCHAR(100),
    arrest                TINYINT(1)    NOT NULL DEFAULT 0,
    domestic              TINYINT(1)    NOT NULL DEFAULT 0,
    PRIMARY KEY (crime_id),
    INDEX idx_crime_area_year_month (community_id, year, month),
    INDEX idx_crime_type            (primary_type),
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id)
);

-- ── (7) crime_aggregations ───────────────────────────────────
-- Monthly crime counts per community area × crime type, 2020-2026.
-- Use this for trend queries — joining crime_records for aggregation is slow.
CREATE TABLE IF NOT EXISTS crime_aggregations (
    community_id  INT         NOT NULL,
    year          SMALLINT    NOT NULL,
    month         TINYINT     NOT NULL,
    primary_type  VARCHAR(50) NOT NULL,
    crime_count   INT         NOT NULL DEFAULT 0,
    PRIMARY KEY (community_id, year, month, primary_type),
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id)
);

-- ── (8) management_companies ─────────────────────────────────
-- Affordable housing management companies.
-- 3NF: phone_number is an attribute of the company, not the housing unit.
CREATE TABLE IF NOT EXISTS management_companies (
    management_company  VARCHAR(255)  NOT NULL,
    phone_number        VARCHAR(20),
    PRIMARY KEY (management_company)
);

-- ── (9) housing_units ────────────────────────────────────────
-- Individual affordable housing developments (~598 rows).
CREATE TABLE IF NOT EXISTS housing_units (
    unit_id             INT          NOT NULL,
    community_id        INT          NOT NULL,
    management_company  VARCHAR(255),
    property_name       VARCHAR(255),
    property_type       VARCHAR(100),
    units               INT,
    address             VARCHAR(255),
    PRIMARY KEY (unit_id),
    FOREIGN KEY (community_id)       REFERENCES community_areas(community_id),
    FOREIGN KEY (management_company) REFERENCES management_companies(management_company)
);

-- ── (10) rail_ridership ──────────────────────────────────────
-- Monthly average ridership per CTA L station, by day type (~129K rows).
-- Day types: W = weekday, A = Saturday, U = Sunday/holiday (CTA convention).
CREATE TABLE IF NOT EXISTS rail_ridership (
    station_id  INT         NOT NULL,
    year        SMALLINT    NOT NULL,
    month       TINYINT     NOT NULL,
    day_type    CHAR(1)     NOT NULL,
    rides       DOUBLE,
    PRIMARY KEY (station_id, year, month, day_type),
    FOREIGN KEY (station_id) REFERENCES cta_rail_stations(station_id)
);

-- ── (11) service_requests ────────────────────────────────────
-- 311 service requests 2022-2026 (~7.7M rows).
-- closed_date retained so response time can be computed:
--   DATEDIFF(closed_date, created_date)
-- response_days is NOT stored (derived attribute per 3NF).
CREATE TABLE IF NOT EXISTS service_requests (
    sr_number     VARCHAR(20)   NOT NULL,
    community_id  INT           NOT NULL,
    created_date  DATE          NOT NULL,
    closed_date   DATE,
    year          SMALLINT      NOT NULL,
    month         TINYINT       NOT NULL,
    request_type  VARCHAR(200),
    status        VARCHAR(50),
    PRIMARY KEY (sr_number),
    INDEX idx_sr_area_year_month (community_id, year, month),
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id)
);

-- ── (12) neighborhood_profiles ───────────────────────────────
-- Pre-materialized 2024 summary per community area — one row per area.
-- Avoids re-aggregating millions of crime/311 rows on every page load.
CREATE TABLE IF NOT EXISTS neighborhood_profiles (
    community_id                  INT          NOT NULL,
    total_population              INT,
    avg_rent                      DECIMAL(10,2),
    crime_rate_per_1000           DECIMAL(10,2),
    service_request_count_2024    INT,
    transit_ridership_monthly_avg DECIMAL(12,0),
    affordable_unit_count         INT          NOT NULL DEFAULT 0,
    PRIMARY KEY (community_id),
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id)
);

-- ── (13) wards ───────────────────────────────────────────────
-- Chicago City Council wards (50 wards, 2023-present boundaries).
CREATE TABLE IF NOT EXISTS wards (
    ward_id           INT         NOT NULL,
    boundary_version  VARCHAR(30) NOT NULL DEFAULT '2023-present',
    PRIMARY KEY (ward_id)
);

-- ── (14) community_area_ward_overlap ─────────────────────────
-- M:N junction: geographic overlap between community areas and wards.
-- Second genuine M:N: verified by GIS overlay of official City of Chicago
-- boundary datasets (cauq-8yn6 × p293-wvbd). 264 overlap pairs across
-- 77 community areas and 50 wards.
CREATE TABLE IF NOT EXISTS community_area_ward_overlap (
    community_id          INT            NOT NULL,
    ward_id               INT            NOT NULL,
    overlap_sq_miles      DECIMAL(10,6)  NOT NULL,
    pct_of_community_area DECIMAL(6,3),
    pct_of_ward           DECIMAL(6,3),
    PRIMARY KEY (community_id, ward_id),
    FOREIGN KEY (community_id) REFERENCES community_areas(community_id),
    FOREIGN KEY (ward_id)      REFERENCES wards(ward_id),
    CHECK (overlap_sq_miles > 0)
);
