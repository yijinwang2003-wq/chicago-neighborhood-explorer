# Query Performance Report

Database: `chicago_neighborhood`

## Benchmark Methodology

- Command: `python3 scripts/analyze_query_performance.py --runs 20`
- Metrics: median/min/max execution time from Python plus raw `EXPLAIN ANALYZE` plans.
- Scope: compares `vw_neighborhood_profile` against `neighborhood_profile_snapshot` for the profile endpoints used by the FastAPI layer.

## Before vs After Summary

| Endpoint | View Median | Snapshot Median | Speedup | Plan Change |
| --- | ---: | ---: | ---: | --- |
| GET /api/neighborhoods | 922.696 ms | 0.830 ms | 1,111.7x | View materializes 2025 aggregates from `crime_records` and `service_requests`; snapshot reads 77 rows and sorts by name. |
| GET /api/neighborhoods/{community_id} | 926.071 ms | 0.104 ms | 8,904.5x | View still materializes all community aggregates before filtering; snapshot uses the `PRIMARY` key on `community_id`. |
| GET /api/compare?ids=1,2,3 | 926.646 ms | 0.145 ms | 6,390.7x | View materializes full aggregate subqueries; snapshot uses a primary-key range scan for the requested IDs. |

Measured with 20 warm local runs unless otherwise specified. Timing is end-to-end database query execution from Python, excluding API serialization and network overhead.

EXPLAIN ANALYZE shows the original view repeatedly scans or materializes large 2025 aggregates, including about 237k `crime_records` rows and about 1.89M `service_requests` rows. The optimized API path reads from `neighborhood_profile_snapshot`, a 77-row table indexed by `community_id`.

## Resume-Ready Performance Bullets

- Optimized the main neighborhood listing endpoint from 922.7 ms to 0.830 ms median latency by replacing repeated analytical view aggregation with an indexed 77-row materialized snapshot.
- Reduced single-neighborhood profile lookup latency from 926.1 ms to 0.104 ms median latency using a primary-key lookup on `community_id`.
- Improved comparison query latency from 926.6 ms to 0.145 ms median latency, a 6,391x speedup for three-community comparisons.
- Eliminated repeated request-time scans over approximately 1.89M service request rows and 237k crime rows for the API profile endpoints.

## Current Performance

Before optimization, API profile endpoints read from `vw_neighborhood_profile`, which joins community metadata to aggregate subqueries over large source tables. The dominant cost is the `service_requests` aggregate, followed by the 2025 `crime_records` aggregate.

After optimization, API profile endpoints read from `neighborhood_profile_snapshot`. The list endpoint scans only 77 snapshot rows, the detail endpoint is a primary-key lookup, and compare uses a primary-key range scan over the requested IDs.

## Potential Optimizations

- Add a scheduled refresh job for `refresh_neighborhood_profile_snapshot` so production data freshness is explicit.
- Benchmark whether `ORDER BY community_name` benefits from forcing `idx_profile_snapshot_name`; current full scan is already bounded to 77 rows.
- Keep the analytical view for ad hoc validation, but route latency-sensitive API traffic to the snapshot table.

## Estimated Improvements

The measured improvements are already in the 1,000x to 8,000x range for the main profile endpoints. Additional indexing of the source tables would help view execution, but it would not beat the bounded 77-row snapshot path for read-heavy API traffic.

## Database Size

| Table | Type | Exact Rows | Estimated Rows | Size MB | Data MB | Index MB |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| service_requests | BASE TABLE | 1885933 | 1871803 | 381.66 | 227.80 | 153.86 |
| crime_records | BASE TABLE | 237274 | 236948 | 51.63 | 25.56 | 26.06 |
| housing_developments | BASE TABLE | 596 | 596 | 0.27 | 0.14 | 0.13 |
| rail_ridership_monthly | BASE TABLE | 1728 | 1728 | 0.17 | 0.13 | 0.05 |
| community_area_ward_overlap | BASE TABLE | 258 | 258 | 0.03 | 0.02 | 0.02 |
| community_areas | BASE TABLE | 77 | 77 | 0.03 | 0.02 | 0.02 |
| cta_lines | BASE TABLE | 8 | 8 | 0.03 | 0.02 | 0.02 |
| cta_rail_stations | BASE TABLE | 144 | 144 | 0.03 | 0.02 | 0.02 |
| management_companies | BASE TABLE | 236 | 236 | 0.03 | 0.02 | 0.02 |
| neighborhood_profile_snapshot | BASE TABLE | 77 | 77 | 0.03 | 0.02 | 0.02 |
| serves | BASE TABLE | 191 | 191 | 0.03 | 0.02 | 0.02 |
| census_profiles | BASE TABLE | 77 | 77 | 0.02 | 0.02 | 0.00 |
| wards | BASE TABLE | 50 | 50 | 0.02 | 0.02 | 0.00 |
| vw_crime_aggregation | VIEW |  | 0 | None | None | None |
| vw_neighborhood_profile | VIEW |  | 0 | None | None | None |
| vw_ward_community_profile | VIEW |  | 0 | None | None | None |

## Indexes

| Table | Index | Unique | Columns |
| --- | --- | --- | --- |
| census_profiles | PRIMARY | True | community_id |
| community_area_ward_overlap | idx_overlap_ward | False | ward_id, pct_of_ward |
| community_area_ward_overlap | PRIMARY | True | community_id, ward_id |
| community_areas | name | True | name |
| community_areas | PRIMARY | True | community_id |
| crime_records | idx_crime_community_date | False | community_id, crime_date |
| crime_records | idx_crime_type_date | False | primary_type, crime_date |
| crime_records | PRIMARY | True | crime_id |
| cta_lines | line_name | True | line_name |
| cta_lines | PRIMARY | True | line_id |
| cta_rail_stations | idx_station_community | False | community_id |
| cta_rail_stations | PRIMARY | True | station_id |
| housing_developments | company_id | False | company_id |
| housing_developments | idx_housing_community | False | community_id |
| housing_developments | idx_housing_coordinates | False | latitude, longitude |
| housing_developments | PRIMARY | True | development_id |
| housing_developments | source_record_key | True | source_record_key |
| management_companies | company_name | True | company_name |
| management_companies | PRIMARY | True | company_id |
| neighborhood_profile_snapshot | idx_profile_snapshot_name | False | community_name |
| neighborhood_profile_snapshot | PRIMARY | True | community_id |
| rail_ridership_monthly | idx_ridership_month_station | False | month_beginning, station_id |
| rail_ridership_monthly | PRIMARY | True | station_id, month_beginning |
| serves | line_id | False | line_id |
| serves | PRIMARY | True | station_id, line_id |
| service_requests | community_id | False | community_id |
| service_requests | idx_service_source_date_community | False | record_source, created_date, community_id, closed_date |
| service_requests | PRIMARY | True | service_request_id |
| service_requests | source_sr_number | True | source_sr_number |
| wards | PRIMARY | True | ward_id |

## Main API Query Metrics

### view baseline GET /api/neighborhoods

Timing:

```json
{
  "runs": 20,
  "returned_rows": 77,
  "min_ms": 917.652,
  "median_ms": 922.696,
  "max_ms": 943.895
}
```

EXPLAIN:

```json
[
  {
    "EXPLAIN": "-> Nested loop left join  (cost=22.2e+9 rows=0) (actual time=1022..1023 rows=77 loops=1)\n    -> Nested loop left join  (cost=67.1e+6 rows=573e+6) (actual time=46.5..46.7 rows=77 loops=1)\n        -> Nested loop left join  (cost=1.95e+6 rows=13.3e+6) (actual time=46..46.2 rows=77 loops=1)\n            -> Nested loop left join  (cost=87757 rows=310002) (actual time=46..46.1 rows=77 loops=1)\n                -> Nested loop left join  (cost=5572 rows=4697) (actual time=45.6..45.7 rows=77 loops=1)\n                    -> Nested loop left join  (cost=34.9 rows=77) (actual time=0.0359..0.0981 rows=77 loops=1)\n                        -> Sort: community_name  (cost=7.95 rows=77) (actual time=0.0333..0.0375 rows=77 loops=1)\n                            -> Table scan on ca  (cost=7.95 rows=77) (actual time=0.00542..0.0166 rows=77 loops=1)\n                        -> Single-row index lookup on cp using PRIMARY (community_id = ca.community_id)  (cost=0.251 rows=1) (actual time=686e-6..707e-6 rows=1 loops=77)\n                    -> Index lookup on cr using <auto_key0> (community_id = ca.community_id)  (cost=31410..31476 rows=263) (actual time=0.592..0.592 rows=1 loops=77)\n                        -> Materialize  (cost=31410..31410 rows=61) (actual time=45.6..45.6 rows=77 loops=1)\n                            -> Group aggregate: count(0)  (cost=31396 rows=61) (actual time=0.713..45.5 rows=77 loops=1)\n                                -> Filter: ((crime_records.crime_date >= TIMESTAMP'2025-01-01 00:00:00') and (crime_records.crime_date < TIMESTAMP'2026-01-01 00:00:00'))  (cost=25331 rows=26322) (actual time=0.00808..40.8 rows=237274 loops=1)\n                                    -> Covering index scan on crime_records using idx_crime_community_date  (cost=25331 rows=236948) (actual time=0.00767..26.6 rows=237274 loops=1)\n                -> Index lookup on h using <auto_key0> (community_id = ca.community_id)  (cost=215..217 rows=10.1) (actual time=0.0049..0.00497 rows=0.857 loops=77)\n                    -> Materialize  (cost=214..214 rows=66) (actual time=0.358..0.358 rows=66 loops=1)\n                        -> Group aggregate: sum(coalesce(housing_developments.reported_unit_count,0))  (cost=199 rows=66) (actual time=0.041..0.34 rows=66 loops=1)\n                            -> Index scan on housing_developments using idx_housing_community  (cost=61.8 rows=596) (actual time=0.039..0.317 rows=596 loops=1)\n            -> Index lookup on st using <auto_key0> (community_id = ca.community_id)  (cost=63.8..66.2 rows=10.3) (actual time=696e-6..745e-6 rows=0.545 loops=77)\n                -> Materialize  (cost=63.6..63.6 rows=43) (actual time=0.0338..0.0338 rows=42 loops=1)\n                    -> Group aggregate: count(0)  (cost=53.7 rows=43) (actual time=0.00542..0.0255 rows=42 loops=1)\n                        -> Filter: (cta_rail_stations.community_id is not null)  (cost=25.1 rows=124) (actual time=0.00458..0.0213 rows=124 loops=1)\n                            -> Covering index range scan on cta_rail_stations using idx_station_community over (NULL < community_id)  (cost=25.1 rows=124) (actual time=0.00421..0.0169 rows=124 loops=1)\n        -> Index lookup on rr using <auto_key0> (community_id = ca.community_id)  (cost=559..562 rows=14.9) (actual time=0.00673..0.00678 rows=0.545 loops=77)\n            -> Materialize  (cost=558..558 rows=43) (actual time=0.5..0.5 rows=42 loops=1)\n                -> Group aggregate: sum(r.month_total)  (cost=548 rows=43) (actual time=0.0257..0.49 rows=42 loops=1)\n                    -> Nested loop inner join  (cost=206 rows=1488) (actual time=0.00712..0.449 rows=1488 loops=1)\n                        -> Filter: (s.community_id is not null)  (cost=25.1 rows=124) (actual time=0.00262..0.0212 rows=124 loops=1)\n                            -> Covering index range scan on s using idx_station_community over (NULL < community_id)  (cost=25.1 rows=124) (actual time=0.00258..0.0163 rows=124 loops=1)\n                        -> Filter: ((r.month_beginning >= DATE'2025-01-01') and (r.month_beginning < DATE'2026-01-01'))  (cost=0.265 rows=12) (actual time=0.00165..0.00298 rows=12 loops=124)\n                            -> Index lookup on r using PRIMARY (station_id = s.station_id)  (cost=0.265 rows=12) (actual time=0.00155..0.00218 rows=12 loops=124)\n    -> Index lookup on sr using <auto_key0> (community_id = ca.community_id)  (cost=0.25..702 rows=2807) (actual time=12.7..12.7 rows=1 loops=77)\n        -> Materialize  (cost=0..0 rows=0) (actual time=976..976 rows=77 loops=1)\n            -> Table scan on <temporary>  (actual time=976..976 rows=77 loops=1)\n                -> Aggregate using temporary table  (actual time=976..976 rows=77 loops=1)\n                    -> Filter: ((service_requests.record_source = 'OPEN_DATA') and (service_requests.created_date >= TIMESTAMP'2025-01-01 00:00:00') and (service_requests.created_date < TIMESTAMP'2026-01-01 00:00:00') and (service_requests.closed_date is not null) and (service_requests.closed_date >= service_requests.created_date))  (cost=187865 rows=280742) (actual time=0.01..628 rows=1.85e+6 loops=1)\n                        -> Covering index range scan on service_requests using idx_service_source_date_community over (record_source = 'OPEN_DATA' AND '2025-01-01 00:00:00' <= created_date < '2026-01-01 00:00:00')  (cost=187865 rows=935901) (actual time=0.00937..335 rows=1.89e+6 loops=1)\n"
  }
]
```

### view baseline GET /api/neighborhoods/{community_id}

Timing:

```json
{
  "runs": 20,
  "returned_rows": 1,
  "min_ms": 916.582,
  "median_ms": 926.071,
  "max_ms": 938.105
}
```

EXPLAIN:

```json
[
  {
    "EXPLAIN": "-> Nested loop left join  (cost=791280 rows=0) (actual time=1021..1021 rows=1 loops=1)\n    -> Nested loop left join  (cost=765041 rows=7.44e+6) (actual time=47..47 rows=1 loops=1)\n        -> Nested loop left join  (cost=18009 rows=173118) (actual time=46.5..46.5 rows=1 loops=1)\n            -> Nested loop left join  (cost=436 rows=4026) (actual time=46.4..46.4 rows=1 loops=1)\n                -> Nested loop left join  (cost=8.6 rows=61) (actual time=46.1..46.1 rows=1 loops=1)\n                    -> Rows fetched before execution  (cost=0..0 rows=1) (actual time=167e-6..334e-6 rows=1 loops=1)\n                    -> Index lookup on cr using <auto_key0> (community_id = 1)  (cost=31410..31413 rows=10) (actual time=46.1..46.1 rows=1 loops=1)\n                        -> Materialize  (cost=31410..31410 rows=61) (actual time=46.1..46.1 rows=77 loops=1)\n                            -> Group aggregate: count(0)  (cost=31396 rows=61) (actual time=0.754..46.1 rows=77 loops=1)\n                                -> Filter: ((crime_records.crime_date >= TIMESTAMP'2025-01-01 00:00:00') and (crime_records.crime_date < TIMESTAMP'2026-01-01 00:00:00'))  (cost=25331 rows=26322) (actual time=0.0122..41.2 rows=237274 loops=1)\n                                    -> Covering index scan on crime_records using idx_crime_community_date  (cost=25331 rows=236948) (actual time=0.0114..26.9 rows=237274 loops=1)\n                -> Index lookup on h using <auto_key0> (community_id = 1)  (cost=215..217 rows=10.1) (actual time=0.359..0.36 rows=1 loops=1)\n                    -> Materialize  (cost=214..214 rows=66) (actual time=0.359..0.359 rows=66 loops=1)\n                        -> Group aggregate: sum(coalesce(housing_developments.reported_unit_count,0))  (cost=199 rows=66) (actual time=0.0389..0.338 rows=66 loops=1)\n                            -> Index scan on housing_developments using idx_housing_community  (cost=61.8 rows=596) (actual time=0.0367..0.315 rows=596 loops=1)\n            -> Index lookup on st using <auto_key0> (community_id = 1)  (cost=63.8..66.2 rows=10.3) (actual time=0.0331..0.0336 rows=1 loops=1)\n                -> Materialize  (cost=63.6..63.6 rows=43) (actual time=0.0327..0.0327 rows=42 loops=1)\n                    -> Group aggregate: count(0)  (cost=53.7 rows=43) (actual time=0.00521..0.0255 rows=42 loops=1)\n                        -> Filter: (cta_rail_stations.community_id is not null)  (cost=25.1 rows=124) (actual time=0.00442..0.0215 rows=124 loops=1)\n                            -> Covering index range scan on cta_rail_stations using idx_station_community over (NULL < community_id)  (cost=25.1 rows=124) (actual time=0.00396..0.0166 rows=124 loops=1)\n        -> Index lookup on rr using <auto_key0> (community_id = 1)  (cost=559..561 rows=10.1) (actual time=0.501..0.502 rows=1 loops=1)\n            -> Materialize  (cost=558..558 rows=43) (actual time=0.501..0.501 rows=42 loops=1)\n                -> Group aggregate: sum(r.month_total)  (cost=548 rows=43) (actual time=0.026..0.492 rows=42 loops=1)\n                    -> Nested loop inner join  (cost=206 rows=1488) (actual time=0.00762..0.45 rows=1488 loops=1)\n                        -> Filter: (s.community_id is not null)  (cost=25.1 rows=124) (actual time=0.00267..0.0213 rows=124 loops=1)\n                            -> Covering index range scan on s using idx_station_community over (NULL < community_id)  (cost=25.1 rows=124) (actual time=0.00237..0.0164 rows=124 loops=1)\n                        -> Filter: ((r.month_beginning >= DATE'2025-01-01') and (r.month_beginning < DATE'2026-01-01'))  (cost=0.265 rows=12) (actual time=0.00164..0.00301 rows=12 loops=124)\n                            -> Index lookup on r using PRIMARY (station_id = s.station_id)  (cost=0.265 rows=12) (actual time=0.00155..0.00218 rows=12 loops=124)\n    -> Index lookup on sr using <auto_key0> (community_id = 1)  (cost=0.25..2.5 rows=10) (actual time=974..974 rows=1 loops=1)\n        -> Materialize  (cost=0..0 rows=0) (actual time=974..974 rows=77 loops=1)\n            -> Table scan on <temporary>  (actual time=974..974 rows=77 loops=1)\n                -> Aggregate using temporary table  (actual time=974..974 rows=77 loops=1)\n                    -> Filter: ((service_requests.record_source = 'OPEN_DATA') and (service_requests.created_date >= TIMESTAMP'2025-01-01 00:00:00') and (service_requests.created_date < TIMESTAMP'2026-01-01 00:00:00') and (service_requests.closed_date is not null) and (service_requests.closed_date >= service_requests.created_date))  (cost=187865 rows=280742) (actual time=0.0109..628 rows=1.85e+6 loops=1)\n                        -> Covering index range scan on service_requests using idx_service_source_date_community over (record_source = 'OPEN_DATA' AND '2025-01-01 00:00:00' <= created_date < '2026-01-01 00:00:00')  (cost=187865 rows=935901) (actual time=0.00958..336 rows=1.89e+6 loops=1)\n"
  }
]
```

### view baseline GET /api/compare?ids=1,2,3

Timing:

```json
{
  "runs": 20,
  "returned_rows": 3,
  "min_ms": 920.596,
  "median_ms": 926.646,
  "max_ms": 938.787
}
```

EXPLAIN:

```json
[
  {
    "EXPLAIN": "-> Nested loop left join  (cost=863e+6 rows=0) (actual time=1022..1022 rows=3 loops=1)\n    -> Nested loop left join  (cost=2.62e+6 rows=22.3e+6) (actual time=46.9..46.9 rows=3 loops=1)\n        -> Nested loop left join  (cost=75963 rows=519354) (actual time=46.4..46.4 rows=3 loops=1)\n            -> Nested loop left join  (cost=3420 rows=12078) (actual time=46.4..46.4 rows=3 loops=1)\n                -> Nested loop left join  (cost=218 rows=183) (actual time=46..46 rows=3 loops=1)\n                    -> Nested loop left join  (cost=2.41 rows=3) (actual time=0.018..0.0282 rows=3 loops=1)\n                        -> Sort: field(ca.community_id,1,2,3)  (cost=1.36 rows=3) (actual time=0.0157..0.017 rows=3 loops=1)\n                            -> Filter: (ca.community_id in (1,2,3))  (cost=1.36 rows=3) (actual time=0.00896..0.0105 rows=3 loops=1)\n                                -> Index range scan on ca using PRIMARY over (community_id = 1) OR (community_id = 2) OR (community_id = 3)  (cost=1.36 rows=3) (actual time=0.00846..0.00983 rows=3 loops=1)\n                        -> Single-row index lookup on cp using PRIMARY (community_id = ca.community_id)  (cost=0.283 rows=1) (actual time=0.00343..0.00353 rows=1 loops=3)\n                    -> Index lookup on cr using <auto_key0> (community_id = ca.community_id)  (cost=31410..31484 rows=263) (actual time=15.3..15.3 rows=1 loops=3)\n                        -> Materialize  (cost=31410..31410 rows=61) (actual time=46..46 rows=77 loops=1)\n                            -> Group aggregate: count(0)  (cost=31396 rows=61) (actual time=0.753..46 rows=77 loops=1)\n                                -> Filter: ((crime_records.crime_date >= TIMESTAMP'2025-01-01 00:00:00') and (crime_records.crime_date < TIMESTAMP'2026-01-01 00:00:00'))  (cost=25331 rows=26322) (actual time=0.0102..41.2 rows=237274 loops=1)\n                                    -> Covering index scan on crime_records using idx_crime_community_date  (cost=25331 rows=236948) (actual time=0.0095..26.9 rows=237274 loops=1)\n                -> Index lookup on h using <auto_key0> (community_id = ca.community_id)  (cost=215..217 rows=10.1) (actual time=0.119..0.12 rows=1 loops=3)\n                    -> Materialize  (cost=214..214 rows=66) (actual time=0.357..0.357 rows=66 loops=1)\n                        -> Group aggregate: sum(coalesce(housing_developments.reported_unit_count,0))  (cost=199 rows=66) (actual time=0.0394..0.339 rows=66 loops=1)\n                            -> Index scan on housing_developments using idx_housing_community  (cost=61.8 rows=596) (actual time=0.0372..0.315 rows=596 loops=1)\n            -> Index lookup on st using <auto_key0> (community_id = ca.community_id)  (cost=63.8..66.2 rows=10.3) (actual time=0.0114..0.0118 rows=0.667 loops=3)\n                -> Materialize  (cost=63.6..63.6 rows=43) (actual time=0.0328..0.0328 rows=42 loops=1)\n                    -> Group aggregate: count(0)  (cost=53.7 rows=43) (actual time=0.00483..0.0254 rows=42 loops=1)\n                        -> Filter: (cta_rail_stations.community_id is not null)  (cost=25.1 rows=124) (actual time=0.00387..0.0215 rows=124 loops=1)\n                            -> Covering index range scan on cta_rail_stations using idx_station_community over (NULL < community_id)  (cost=25.1 rows=124) (actual time=0.00363..0.0169 rows=124 loops=1)\n        -> Index lookup on rr using <auto_key0> (community_id = ca.community_id)  (cost=559..562 rows=14.9) (actual time=0.169..0.169 rows=0.667 loops=3)\n            -> Materialize  (cost=558..558 rows=43) (actual time=0.504..0.504 rows=42 loops=1)\n                -> Group aggregate: sum(r.month_total)  (cost=548 rows=43) (actual time=0.0257..0.495 rows=42 loops=1)\n                    -> Nested loop inner join  (cost=206 rows=1488) (actual time=0.00704..0.453 rows=1488 loops=1)\n                        -> Filter: (s.community_id is not null)  (cost=25.1 rows=124) (actual time=0.00229..0.0208 rows=124 loops=1)\n                            -> Covering index range scan on s using idx_station_community over (NULL < community_id)  (cost=25.1 rows=124) (actual time=0.00229..0.0166 rows=124 loops=1)\n                        -> Filter: ((r.month_beginning >= DATE'2025-01-01') and (r.month_beginning < DATE'2026-01-01'))  (cost=0.265 rows=12) (actual time=0.00166..0.00302 rows=12 loops=124)\n                            -> Index lookup on r using PRIMARY (station_id = s.station_id)  (cost=0.265 rows=12) (actual time=0.00156..0.00219 rows=12 loops=124)\n    -> Index lookup on sr using <auto_key0> (community_id = ca.community_id)  (cost=0.25..702 rows=2807) (actual time=325..325 rows=1 loops=3)\n        -> Materialize  (cost=0..0 rows=0) (actual time=975..975 rows=77 loops=1)\n            -> Table scan on <temporary>  (actual time=975..975 rows=77 loops=1)\n                -> Aggregate using temporary table  (actual time=975..975 rows=77 loops=1)\n                    -> Filter: ((service_requests.record_source = 'OPEN_DATA') and (service_requests.created_date >= TIMESTAMP'2025-01-01 00:00:00') and (service_requests.created_date < TIMESTAMP'2026-01-01 00:00:00') and (service_requests.closed_date is not null) and (service_requests.closed_date >= service_requests.created_date))  (cost=187865 rows=280742) (actual time=0.0106..627 rows=1.85e+6 loops=1)\n                        -> Covering index range scan on service_requests using idx_service_source_date_community over (record_source = 'OPEN_DATA' AND '2025-01-01 00:00:00' <= created_date < '2026-01-01 00:00:00')  (cost=187865 rows=935901) (actual time=0.00917..336 rows=1.89e+6 loops=1)\n"
  }
]
```

### snapshot GET /api/neighborhoods

Timing:

```json
{
  "runs": 20,
  "returned_rows": 77,
  "min_ms": 0.814,
  "median_ms": 0.83,
  "max_ms": 1.281
}
```

EXPLAIN:

```json
[
  {
    "EXPLAIN": "-> Sort: neighborhood_profile_snapshot.community_name  (cost=7.95 rows=77) (actual time=0.0489..0.0573 rows=77 loops=1)\n    -> Table scan on neighborhood_profile_snapshot  (cost=7.95 rows=77) (actual time=0.00533..0.0335 rows=77 loops=1)\n"
  }
]
```

### snapshot GET /api/neighborhoods/{community_id}

Timing:

```json
{
  "runs": 20,
  "returned_rows": 1,
  "min_ms": 0.094,
  "median_ms": 0.104,
  "max_ms": 0.164
}
```

EXPLAIN:

```json
[
  {
    "EXPLAIN": "-> Rows fetched before execution  (cost=0..0 rows=1) (actual time=83e-6..125e-6 rows=1 loops=1)\n"
  }
]
```

### snapshot GET /api/compare?ids=1,2,3

Timing:

```json
{
  "runs": 20,
  "returned_rows": 3,
  "min_ms": 0.132,
  "median_ms": 0.145,
  "max_ms": 0.22
}
```

EXPLAIN:

```json
[
  {
    "EXPLAIN": "-> Sort: field(neighborhood_profile_snapshot.community_id,1,2,3)  (cost=1.36 rows=3) (actual time=0.00592..0.00617 rows=3 loops=1)\n    -> Filter: (neighborhood_profile_snapshot.community_id in (1,2,3))  (cost=1.36 rows=3) (actual time=0.00262..0.00413 rows=3 loops=1)\n        -> Index range scan on neighborhood_profile_snapshot using PRIMARY over (community_id = 1) OR (community_id = 2) OR (community_id = 3)  (cost=1.36 rows=3) (actual time=0.00246..0.00383 rows=3 loops=1)\n"
  }
]
```
