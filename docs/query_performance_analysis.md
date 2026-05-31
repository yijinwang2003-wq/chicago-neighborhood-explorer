# Query Performance Analysis

This report covers the primary SQL paths used by:

- `GET /api/neighborhoods`
- `GET /api/neighborhoods/{community_id}`
- `GET /api/compare?ids=1,2,3`

The profile endpoints have been optimized to read from
`neighborhood_profile_snapshot`, a 77-row materialized table refreshed from
`vw_neighborhood_profile`. The original analytical view remains intact.

The live MySQL server was not reachable during this run, so this document
combines static analysis from the committed schema/views/indexes with exact row
counts from `report_assets/row_count_log.txt`. To generate live before/after
`EXPLAIN` and timing metrics, run:

```bash
python3 scripts/analyze_query_performance.py --runs 10
```

The script writes `docs/query_performance_report.md` and does not modify data.
If the snapshot table exists, it benchmarks both the old view baseline and the
new snapshot query path.

## Main SQL Queries

### Current: `GET /api/neighborhoods`

```sql
SELECT <profile_columns>
FROM neighborhood_profile_snapshot
ORDER BY community_name;
```

### Current: `GET /api/neighborhoods/{community_id}`

```sql
SELECT <profile_columns>
FROM neighborhood_profile_snapshot
WHERE community_id = ?;
```

### Current: `GET /api/compare?ids=1,2,3`

```sql
SELECT <profile_columns>
FROM neighborhood_profile_snapshot
WHERE community_id IN (?, ?, ?)
ORDER BY FIELD(community_id, ?, ?, ?);
```

Before the optimization, all three queries read directly from
`vw_neighborhood_profile`.

## View Logic

`vw_neighborhood_profile` starts from the 77-row `community_areas` table and
left joins derived aggregates:

- `census_profiles` by primary key `community_id`
- 2025 crime counts from `crime_records`
- affordable housing units from `housing_developments`
- station counts from `cta_rail_stations`
- 2025 ridership totals from `rail_ridership_monthly`
- 2025 closed 311 response time from `service_requests`

The expensive work happens inside the aggregate subqueries, especially
`service_requests` and `crime_records`.

## Existing Row Counts

| Table | Rows |
| --- | ---: |
| `service_requests` | 1,885,931 |
| `crime_records` | 237,274 |
| `rail_ridership_monthly` | 1,728 |
| `housing_developments` | 596 |
| `community_area_ward_overlap` | 258 |
| `management_companies` | 236 |
| `serves` | 191 |
| `cta_rail_stations` | 144 |
| `community_areas` | 77 |
| `census_profiles` | 77 |
| `wards` | 50 |
| `cta_lines` | 8 |

Total base-table rows: **2,126,570**.

## Existing Indexes

| Table | Index | Columns | Used By |
| --- | --- | --- | --- |
| `community_areas` | primary key | `community_id` | profile joins and filters |
| `census_profiles` | primary key | `community_id` | profile join |
| `crime_records` | `idx_crime_community_date` | `community_id`, `crime_date` | community-specific crime filters |
| `crime_records` | `idx_crime_type_date` | `primary_type`, `crime_date` | crime-type analysis |
| `housing_developments` | `idx_housing_community` | `community_id` | housing aggregate |
| `cta_rail_stations` | `idx_station_community` | `community_id` | station aggregate |
| `rail_ridership_monthly` | primary key | `station_id`, `month_beginning` | station-month lookup |
| `rail_ridership_monthly` | `idx_ridership_month_station` | `month_beginning`, `station_id` | 2025 ridership aggregate |
| `service_requests` | `idx_service_source_date_community` | `record_source`, `created_date`, `community_id`, `closed_date` | 2025 311 response aggregate |
| `neighborhood_profile_snapshot` | primary key | `community_id` | detail and compare endpoints |
| `neighborhood_profile_snapshot` | `idx_profile_snapshot_name` | `community_name` | neighborhood list ordering |

## Current Performance

### Before: View-backed API Reads

- `/api/neighborhoods` returns only 77 rows, but view execution must compute
  aggregate subqueries over the large base tables.
- `/api/neighborhoods/{community_id}` has a `community_id` predicate, but MySQL
  may still materialize the full view before applying the outer filter because
  the view contains grouped derived tables.
- `/api/compare` returns only a few rows but has the same view materialization
  risk as the detail endpoint.
- The biggest cost center is the 2025 311 aggregate over **1.89M**
  `service_requests` rows.
- The second largest cost center is the 2025 crime aggregate over **237K**
  `crime_records` rows.

### After: Snapshot-backed API Reads

- `/api/neighborhoods` scans and sorts the 77-row
  `neighborhood_profile_snapshot` table.
- `/api/neighborhoods/{community_id}` uses a primary-key lookup on
  `community_id`.
- `/api/compare` uses indexed lookups for the requested community IDs and
  returns only the selected rows.
- Expensive 311/crime/housing/transit aggregates are computed only when
  `refresh_neighborhood_profile_snapshot()` is called.
- The API read path no longer repeatedly aggregates the 1.89M-row
  `service_requests` table or 237K-row `crime_records` table.

Live metrics still need to be collected with `EXPLAIN ANALYZE` once MySQL is
running.

## Snapshot Refresh Strategy

The snapshot is defined in:

```text
sql/05_create_profile_snapshot.sql
```

Refresh command:

```sql
CALL refresh_neighborhood_profile_snapshot();
```

The script creates `neighborhood_profile_snapshot`, adds a primary key on
`community_id`, adds an index on `community_name`, and loads it from
`vw_neighborhood_profile`. It does not delete or replace the original view.

## Potential Optimizations

### 1. Add generated year columns for date filtering

Current filters use date ranges, which are indexable, but the profile view
always computes 2025 aggregates. A generated year column can make annual
analytics easier to index and reason about:

```sql
ALTER TABLE service_requests
  ADD COLUMN created_year SMALLINT GENERATED ALWAYS AS (YEAR(created_date)) STORED,
  ADD INDEX idx_sr_source_year_community_closed
    (record_source, created_year, community_id, closed_date);

ALTER TABLE crime_records
  ADD COLUMN crime_year SMALLINT GENERATED ALWAYS AS (YEAR(crime_date)) STORED,
  ADD INDEX idx_crime_year_community
    (crime_year, community_id);
```

This is a schema change, so treat it as a future optimization rather than a
deployment requirement.

### 2. Add covering indexes for the profile aggregates

The current 311 index is useful for filtering, but the aggregate also needs
`created_date`, `closed_date`, and `community_id`. A covering-style index tuned
for the view would be:

```sql
CREATE INDEX idx_sr_profile_2025
ON service_requests (record_source, created_date, community_id, closed_date);
```

This already exists as `idx_service_source_date_community`, so the current
schema is well aligned for the profile view.

For crime:

```sql
CREATE INDEX idx_crime_date_community
ON crime_records (crime_date, community_id);
```

This may be better than `(community_id, crime_date)` for citywide yearly
aggregates because the view filters by date and groups by community.

### 3. Rewrite detail and compare queries to push filters into aggregates

This is now lower priority because the public profile endpoints read from the
snapshot. It would still be useful for any future endpoint that must read live
view data without using the snapshot.

Expected benefit:

- `/api/neighborhoods/{id}` can aggregate only one community area.
- `/api/compare` can aggregate only the requested communities.
- This avoids unnecessary full-view materialization for small result sets.

### 4. Materialize the profile view for demo workloads

Implemented via `neighborhood_profile_snapshot`. Because the profile output is
only 77 rows and changes rarely, the three endpoints are now mostly small-table
reads or primary-key lookups:

```sql
CALL refresh_neighborhood_profile_snapshot();
```

This is the highest-impact optimization for portfolio demo latency.

## Estimated Improvements

| Optimization | Endpoint Impact | Estimated Improvement |
| --- | --- | --- |
| `idx_crime_date_community` | profile view crime aggregate | lower scanned crime index range for citywide 2025 aggregation |
| filter-pushed detail SQL | `/api/neighborhoods/{id}` | high improvement when MySQL currently materializes full view |
| filter-pushed compare SQL | `/api/compare` | high improvement for small ID lists |
| materialized profile snapshot | all three endpoints | reduces endpoint DB work to 77-row scan or PK lookups |

Resume-safe phrasing after live measurement:

- "Optimized profile API from repeated analytical view aggregation over 2.1M+ source rows to indexed reads from a 77-row snapshot table."
- "Added MySQL indexing strategy around 1.9M-row 311 table and 237K-row crime table."
- "Built repeatable EXPLAIN/timing benchmark script for FastAPI-backed SQL endpoints."
- After running the script, replace these with measured values such as
  "reduced median query latency from X ms to Y ms" or
  "reduced scanned rows from X to Y for detail/compare endpoints."
