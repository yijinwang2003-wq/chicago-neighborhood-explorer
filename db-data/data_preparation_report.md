# Data Preparation Report — Chicago Neighborhood Intelligence
**MPCS 53001 Databases | Final Project Step 3**
**Role:** Data Pipeline Lead
**Script:** `etl_pipeline.py` (PySpark) + `compute_ward_overlap.py` (GIS)
**Output:** `projectDatabases/` — 14 MySQL-ready CSV tables

---

## 1. Overview

This report documents the data collection, cleaning, and ETL pipeline work that produced
the 14-table MySQL dataset for the Chicago Neighborhood Intelligence application. The
pipeline transforms raw Chicago open-data CSV snapshots into normalized, validated tables
ready to load into MySQL using `schema.sql` + `load_data.sql`.

**Pipeline stack:**

| Layer | Technology | Version |
|---|---|---|
| Distributed compute | Apache Spark | 4.1.1 (PySpark) |
| Runtime | Python | 3.13 |
| JVM | Java | 18 |
| Geospatial processing | shapely | 2.x |
| In-memory tabular work | pandas | 2.3.x |
| Output format | CSV + Parquet | — |

**Data flow:**

```
Chicago Data Portal CSV snapshots  (11 source files, ~10 GB total)
              |
              v
   PySpark / pandas staging
              |
              v
   Cleaning, deduplication, spatial joins, normalization
              |
              v
   projectDatabases/  (14 MySQL-ready CSV + Parquet folders)
              |
              v
   load_data.sql  →  MySQL  (chicago_neighborhood database)
```

The two M:N relationships in the schema:
- `serves` — CTA rail stations × rail lines (which lines stop at which station)
- `community_area_ward_overlap` — Chicago community areas × city council wards (GIS overlap)

---

## 2. Data Collection

All source data was downloaded from the **Chicago Data Portal** (data.cityofchicago.org)
as CSV snapshots in May 2026. No API calls are made at runtime — the pipeline reads from
local files only.

| Source File | Dataset ID | Downloaded | Raw Size | Raw Rows | Used For |
|---|---|---|---|---|---|
| `Boundaries_-_Community_Areas_20260502.csv` | `igwz-8jzy` | 2026-05-02 | 1.9 MB | 77 | Community area names, polygons, area |
| `CCA_2025.csv` | CMAP ACS 5-year | 2026-05-02 | 138 KB | 77 | Demographic and income data per area |
| `CTA_-_System_Information_-_List_of_'L'_Stops_20260503.csv` | `8pix-ypme` | 2026-05-03 | 55 KB | 302 | CTA L station names, coordinates, lines |
| `CTA_-_Ridership_-_'L'_Station_Entries_-_Monthly_..._20260502.csv` | `5neh-572f` | 2026-05-02 | 3.0 MB | 43,078 | Monthly L ridership by station and day type |
| `Crimes_-_2001_to_Present_20260502.csv` | `ijzp-q8t2` | 2026-05-02 | 2.2 GB | 8,543,004 | Crime incident records |
| `311_Service_Requests_20260502.csv` | `v6vf-nfxy` | 2026-05-02 | 5.6 GB | 13,777,927 | 311 service request records |
| `Affordable_Rental_Housing_Developments_20260503.csv` | `s6ha-ppgi` | 2026-05-03 | 131 KB | 598 | Affordable housing developments |
| `Business_Licenses_-_Current_Active_20260505.csv` | `uupf-x98q` | 2026-05-05 | 24 MB | 54,210 | Active food and bar business licenses |
| `CPD_Parks_20260505.csv` | `ejsh-fztr` | 2026-05-05 | 1.9 MB | 617 | Parks with acreage and polygon boundaries |
| `Libraries_-_Locations_20260505.csv` | `x8fc-8rcq` | 2026-05-05 | 21 KB | 81 | Library branch locations |
| `Boundaries_-_Wards_(2023-)_20260524.csv` | City of Chicago | 2026-05-24 | 3.3 MB | 50 | City council ward boundaries (2023 redistricting) |
| `CTA_-_Ridership_-_Bus_Routes_-_Daily_Totals_20260502.csv` | `jyb9-n7fm` | 2026-05-02 | 32 MB | 1,102,973 | Bus ridership — **excluded** (no geographic join key) |

**Year filters applied:**

Two large datasets cover decades of history but not all years are needed. Filters were
chosen to balance data volume with analytical relevance:

- **`crime_records`**: filtered to 2020–2026. Reason: the post-pandemic period (2020–) is
  a coherent analytical window, and loading all 8.5M records (2001–2026) into MySQL would
  produce a table too large for practical demo queries. The `crime_aggregations` table
  covers the full 2020–2026 window for year-over-year trend analysis.

- **`service_requests`**: filtered to 2022–2026. Reason: the oldest reference in the
  project's sample queries is 2023; keeping 4 full years provides enough history for
  trend analysis while keeping the table under 8M rows.

---

## 3. Data Cleaning

The following quality issues were discovered and fixed during pipeline development:

---

### Issue 1: `census_profiles` joined on wrong key — silent data corruption (Critical)

**Problem:** The script initially joined `census_profiles` to `community_areas` using
CCA_2025's `OBJECTID` column. `OBJECTID` is a shapefile row counter (1, 2, 3...) and
does NOT map to Chicago's official community area numbers. This produced silent data
corruption: for example, CCA row 3 has `OBJECTID=3, GEOID=77` (Edgewater), while
Boundaries `AREA_NUMBE=3` is Uptown — joining on OBJECTID would have assigned Edgewater's
demographics to Uptown's record for every misaligned row.

**Fix:** Changed the join key from `OBJECTID` to `GEOID`. `GEOID` is the official Chicago
community area number (1–77) and matches `AREA_NUMBE` in the Boundaries file across all
77 rows.

**Why it was missed:** A spot-check on community area 26 (Austin) passed because Austin
has `OBJECTID = GEOID = 26`. Edgewater (`OBJECTID=3, GEOID=77`) was the first divergence.

---

### Issue 2: Comma thousands-separators in numeric columns

**Problem:** Several columns use comma-formatted numbers (e.g., `SHAPE_AREA = "51,259,902.4506"`,
ridership values like `"6,233.9"`, park acreage like `"12,450.5"`). PySpark's `.cast("double")`
returns NULL for every row when the string contains commas.

**Fix:** Applied `F.regexp_replace(F.col(colname), ",", "")` before casting to double.
Affected columns: `SHAPE_AREA` (Boundaries CSV), `AVG_WEEKDAY_RIDES`, `AVG_SATURDAY_RIDES`,
`AVG_SUNDAY-HOLIDAY_RIDES` (CTA Monthly CSV), and park acreage (CPD Parks CSV).

---

### Issue 3: `service_requests` DUPLICATE filter dropped rows with NULL values

**Problem:** The filter `F.lower(F.col("DUPLICATE")) != "true"` evaluates to NULL (not
`True`) when `DUPLICATE` is NULL. PySpark's filter silently discards NULL-valued rows,
meaning non-duplicate records with a missing DUPLICATE field were lost.

**Fix:** Changed to `F.col("DUPLICATE").isNull() | (F.lower(F.col("DUPLICATE")) != "true")`.
This correctly retains all rows that are not confirmed duplicates.

---

### Issue 4: DST gap caused datetime parse failures

**Problem:** Chicago observes Daylight Saving Time. During the spring-forward hour
(2:00–2:59 AM), dates in the crime CSV become invalid in the `America/Chicago` timezone.
PySpark's `to_timestamp()` with timezone raises `DateTimeException` for these rows.

**Fix:** Parsed `Date` as a date-only string using `to_date()` instead of `to_timestamp()`.
Time-of-day precision is not needed for any query in this project.

---

### Issue 5: UTF-8 BOM in CCA_2025.csv first column

**Problem:** The CCA_2025 demographic file has a UTF-8 Byte Order Mark (BOM) at the start
of the file. PySpark reads the first column name as `﻿OBJECTID` instead of `OBJECTID`,
breaking all column references to that field.

**Fix:** Used `GEOID` as the join key (which has no BOM issue) rather than `OBJECTID`.
The BOM-affected column is never directly referenced.

---

### Issue 6: Shapely axis order (longitude vs latitude)

**Problem:** The shapely `Point` constructor takes `(x, y)` i.e. `(longitude, latitude)`.
The CTA Stops CSV columns are named `Lon` and `Lat` — easy to swap. Swapping produces
points in the Atlantic Ocean rather than Chicago, causing all spatial join lookups to fail.

**Fix:** Always constructed `Point(lon, lat)` — longitude first. Added an assertion that
all resulting community_id values are in 1–77 before writing output.

---

### Issue 7: L station stops at polygon boundaries return NULL community_id

**Problem:** shapely's `.contains()` is strict — a point exactly on a polygon edge is not
"inside" any polygon. Several CTA L stops sit exactly on community area boundaries and
return NULL from the point-in-polygon test.

**Fix:** Added a nearest-polygon fallback: for any station where `.contains()` returns NULL,
find the closest polygon by centroid distance and assign that community_id instead. This
produced 100% coverage (0 NULL community_ids) across all 144 stations.

---

### Issue 8: CTA monthly ridership column name contains a hyphen

**Problem:** The column `avg_sunday-holiday_rides` contains a hyphen, which is an invalid
character in PySpark column expressions. Any `col("avg_sunday-holiday_rides")` call raises
`AnalysisException`.

**Fix:** Renamed via `withColumnRenamed` before any `col()` reference.

---

### Issue 9: Crime deduplication required before both output tables

**Problem:** The 8.5M-row crime CSV contains duplicate records (same Case Number across
multiple rows due to updates to existing reports). Loading duplicates inflates row counts
and distorts aggregate crime statistics.

**Fix:** Applied a `row_number()` window function partitioned by `Case Number`, ordered by
`Updated On` descending, keeping only `rn = 1` (the most recent record per case). The
deduplication runs once on the filtered 2020–2026 subset and the result is cached before
both `crime_records` and `crime_aggregations` are derived from it.

---

## 4. ETL Pipeline Design

### Architecture

```
Source CSVs
    │
    ├─ Small files (< 5 MB) ──────────► pandas DataFrames
    │   Community areas, CTA stops,          │
    │   CTA lines, Housing, Libraries,       ▼
    │   Parks, Wards                   shapely spatial joins
    │                                        │
    └─ Large files (> 100 MB) ──────► PySpark DataFrames
        Crimes, 311, CTA ridership           │
                                             ▼
                                    Transformations & dedup
                                             │
                                             ▼
                               projectDatabases/<table>/
                                   ├── csv/data.csv    ← MySQL load
                                   └── parquet/        ← Python inspection
```

### Per-domain transformations

**Community areas**
- Read 77-row Boundaries CSV; parse `the_geom` (WKT MULTIPOLYGON) into shapely objects
- Convert `SHAPE_AREA` (comma-formatted, in square feet) → square miles
- Compute `centroid_lat`, `centroid_lng` from each polygon for display and distance queries
- Output: `community_areas` (77 rows, 5 columns)

**Census profiles**
- Read CCA_2025.csv (220 columns); select 6 demographic columns needed by the schema
- Join to community areas on `GEOID` → `community_id`
- Output: `census_profiles` (77 rows, 6 columns)

**CTA rail stations**
- Read 302-row stop-level CSV; deduplicate to station level by grouping on `MAP_ID`
  (each physical station has 2 directional stops — N/S or E/W bound)
- Line membership aggregated with boolean OR: station serves a line if either direction does
- Assign `community_id` via point-in-polygon spatial join; nearest-polygon fallback for edge cases
- Output: `cta_rail_stations` (144 rows, 6 columns)

**CTA lines**
- Hardcoded from CTA documentation: 8 lines (Red, Blue, Green, Brown, Pink, Orange, Purple, Yellow)
- Output: `cta_lines` (8 rows, 2 columns)

**Serves (M:N #1 — stations × lines)**
- Pivot the boolean line columns from `cta_rail_stations` into long format: one row per (station_id, line_id) pair where the station serves that line
- Output: `serves` (191 rows, 2 columns)

**Crime records**
- Read 8.5M-row CSV with PySpark; filter to year 2020–2026
- Deduplicate by Case Number using `row_number()` window (keep most recent update per case)
- Validate `Community Area` column: filter out rows where community_id is NULL or outside 1–77
- Parse date strings (MM/DD/YYYY HH:MM:SS AM/PM) to MySQL-compatible DATETIME
- Cache the result; derive both `crime_records` and `crime_aggregations` from the cache
- Output: `crime_records` (1,487,886 rows, 11 columns)

**Crime aggregations**
- Derived from the cached 2020–2026 crime DataFrame (same dedup applied)
- `GROUP BY community_id, year, month, primary_type` → `SUM(1) AS crime_count`
- Output: `crime_aggregations` (92,329 rows, 5 columns)

**Management companies (3NF split)**
- Read 598-row Affordable Housing CSV; extract `management_company` + `phone_number`
- Deduplicate on company name (keep first phone seen); addresses the transitive dependency
  `unit_id → management_company → phone_number` identified in Step 2 normalization
- Output: `management_companies` (236 rows, 2 columns)

**Housing units**
- Same source as above; keep all 598 development rows
- `management_company` column serves as FK to `management_companies`
- Output: `housing_units` (598 rows, 7 columns)

**Rail ridership (wide-to-long unpivot)**
- Read 43,078-row CTA Monthly CSV
- Strip comma thousands-separators from ridership columns before casting
- Unpivot 3 day-type columns (avg_weekday_rides, avg_saturday_rides, avg_sunday-holiday_rides)
  into a single `rides` column with a `day_type` column (W/A/U)
- Output: `rail_ridership` (129,234 rows, 5 columns; 3× the source rows)

**Service requests**
- Read 13.7M-row 311 CSV with PySpark; filter to `created_date` year 2022–2026
- Remove confirmed duplicates (NULL-safe filter on `DUPLICATE` column)
- Keep only columns needed by the schema: `sr_number`, `community_id`, `created_date`,
  `closed_date`, `year`, `month`, `request_type`, `status`
- Output: `service_requests` (7,763,457 rows, 8 columns)

**Wards**
- Read 50-row Wards Boundaries CSV (2023 redistricting)
- Extract `ward_id` and `boundary_version`
- Output: `wards` (50 rows, 2 columns)

**Community area ward overlap (M:N #2 — areas × wards)**
- Compute pairwise GIS intersection of all 77 community area polygons × all 50 ward polygons
- For each intersecting pair: compute `overlap_sq_miles`, `pct_of_community_area`, `pct_of_ward`
- Filter out pairs with zero overlap (i.e., non-adjacent areas and wards)
- Script: `compute_ward_overlap.py`
- Output: `community_area_ward_overlap` (264 rows, 5 columns)

**Neighborhood profiles**
- Materialized 2024 summary per community area, derived from all tables above
- Columns: `total_population`, `avg_rent`, `crime_rate_per_1000`, `service_request_count_2024`,
  `transit_ridership_monthly_avg`, `affordable_unit_count`
- All values derived at pipeline time so the UI can query a single table for overview cards
- Output: `neighborhood_profiles` (77 rows, 7 columns)

---

## 5. Output Tables

All 14 tables link to `community_areas` via `community_id` (integer 1–77).

| Table | PK | Rows | Columns | Description |
|---|---|---:|---|---|
| `community_areas` | `community_id` | 77 | `community_id, name, centroid_lat, centroid_lng, area_sq_miles` | Chicago's 77 community areas — geographic anchor |
| `census_profiles` | `community_id` | 77 | `community_id, total_population, median_household_income, median_rent, transit_share_pct, pop_density_per_acre` | 2025 ACS demographics |
| `cta_rail_stations` | `station_id` | 144 | `station_id, station_name, community_id, latitude, longitude, ada` | CTA L stations with area assignment |
| `cta_lines` | `line_id` | 8 | `line_id, line_name` | 8 CTA rail lines |
| `serves` (**M:N #1**) | `(station_id, line_id)` | 191 | `station_id, line_id` | Which lines serve which stations |
| `crime_records` | `crime_id` | **1,487,886** | `crime_id, case_number, community_id, date, year, month, primary_type, description, location_description, arrest, domestic` | Individual crime incidents 2020–2026 |
| `crime_aggregations` | auto | 92,329 | `community_id, year, month, primary_type, crime_count` | Monthly crime counts 2020–2026 |
| `management_companies` | `management_company` | 236 | `management_company, phone_number` | Affordable housing operators |
| `housing_units` | `unit_id` | 598 | `unit_id, community_id, management_company, property_name, property_type, units, address` | Individual developments |
| `rail_ridership` | auto | 127,674 | `station_id, year, month, day_type, rides` | Monthly avg rides per station by day type |
| `service_requests` | `sr_number` | **7,763,457** | `sr_number, community_id, created_date, closed_date, year, month, request_type, status` | 311 requests 2022–2026 |
| `neighborhood_profiles` | `community_id` | 77 | `community_id, total_population, avg_rent, crime_rate_per_1000, service_request_count_2024, transit_ridership_monthly_avg, affordable_unit_count` | Pre-materialized 2024 area summary |
| `wards` | `ward_id` | 50 | `ward_id, boundary_version` | 50 city council wards (2023 boundaries) |
| `community_area_ward_overlap` (**M:N #2**) | `(community_id, ward_id)` | 264 | `community_id, ward_id, overlap_sq_miles, pct_of_community_area, pct_of_ward` | GIS-computed geographic overlap |

**500K+ requirement:** `crime_records` has 1,487,886 rows and `service_requests` has
7,763,457 rows — both independently satisfy the grading requirement.

**M:N relationships:**
- `serves`: a station can be served by multiple lines (e.g., Clark/Lake serves Red, Blue,
  Green, Brown, Pink, Orange, Purple). A line serves multiple stations.
- `community_area_ward_overlap`: a community area (e.g., Hyde Park) overlaps multiple wards
  (5, 7, 8); a ward overlaps multiple community areas.

**Why `wards` replaced `near_stop`:** Step 2 designed a `near_stop` table (housing units ×
CTA stations, distance < 1000m) as a second M:N relationship. The Step 2 grader noted:
"this is not an efficient implementation... in reality you can just store the lat/long and
compute distance at query time." The `wards`/`community_area_ward_overlap` relationship
was added instead — it captures a genuine, non-derivable geographic fact (ward boundary
overlap cannot be computed from the data already in other tables) and serves real
analytical use cases such as ward-level policy queries.

---

## 6. Known Limitations

| Limitation | Detail |
|---|---|
| Crime records: 2020–2026 only | Pre-2020 incidents not in `crime_records`. Widen the year filter in `etl_pipeline.py` if historical data is needed. |
| 311 requests: 2022–2026 only | Pre-2022 requests not included. |
| `response_days` not stored | Per 3NF design — compute at query time: `DATEDIFF(closed_date, created_date)`. NULL when `closed_date` is NULL (open requests). |
| Bus ridership excluded | The CTA bus ridership CSV contains only route/date/rides — no station or community area field. Cannot be joined to any table in the schema. Bus transit is therefore unrepresented. |
| CTA L coverage | Not all 77 community areas have a CTA L station within their boundary. `transit_ridership_monthly_avg` in `neighborhood_profiles` will be NULL for these areas. |
| `rail_ridership` rows are averages | `rides` stores the average ridership for that day type in that month, not the total. Multiply by approximate days in the month if totals are needed. |
| Management company phone dedup | Where the same management company appears with different phone numbers across properties, the first phone seen is kept. A small number of companies are affected. |
| Ward data: geometry only | `wards` stores `ward_id` and `boundary_version`. Alderman names and contact info are not included (not in the boundaries dataset). |
| `transit_share_pct` is a fraction | `census_profiles.transit_share_pct` is stored as a decimal (0–1), not a percentage (0–100). Example: 0.43 = 43% of commuters use transit. Write SQL as `WHERE transit_share_pct > 0.30`. |
| Riverdale ward overlap is 96.3% | Riverdale (community_id=54) sums to 96.3% rather than 100% due to a sliver at the city boundary that falls outside any ward polygon. Acceptable GIS precision artifact. |
