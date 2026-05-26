# Teammate Quickstart — Chicago Neighborhood Intelligence
**MPCS 53001 Databases | Final Project Step 3**

This is the only doc you need to read. Follow the steps in order and you will have
the full database loaded in MySQL with 14 tables and 10+ million rows.

---

## Prerequisites

| Requirement | Check command | Minimum version |
|---|---|---|
| MySQL | `mysql --version` | 8.0+ |
| Python (optional, for GUI app) | `python3 --version` | 3.10+ |

If MySQL is not installed, download from: https://dev.mysql.com/downloads/mysql/

---

## Step 1 — Download and extract the data

1. Download `chicago_neighborhood_data.zip` from the shared Google Drive link:
   **https://drive.google.com/file/d/16QN7a0xuqZwWiL_wNfb5323kPVcibsiT/view?usp=share_link**

2. Extract the zip. You should get a folder called `chicago_neighborhood_data/`
   containing 14 CSV files.

3. Note the **full absolute path** to that folder. You will need it in Step 3.

   Mac example:  `/Users/yourname/Downloads/chicago_neighborhood_data`
   Windows example: `C:/Users/yourname/Downloads/chicago_neighborhood_data`

---

## Step 2 — Create the database tables

From the `step3/` project folder (or wherever you have `schema.sql`):

```bash
mysql -u root -p < schema/create_tables.sql
```

Or using the `schema.sql` from `projectDatabases/`:

```bash
mysql -u root -p < /path/to/projectDatabases/schema.sql
```

Enter your MySQL root password when prompted.

Expected output: 14 `CREATE TABLE` statements complete with no errors, database `chicago_neighborhood` created.

Verify with:
```sql
USE chicago_neighborhood;
SHOW TABLES;
-- Should list 14 tables
```

---

## Step 3 — Fix the data path (run once, takes 5 seconds)

The `load_data.sql` script uses a placeholder `/REPLACE_WITH_YOUR_DATA_PATH` that must
be replaced with the actual path to your extracted zip folder.

**Run this one command** from the `projectDatabases/` folder, substituting your real path:

```bash
# Mac / Linux:
sed 's|/REPLACE_WITH_YOUR_DATA_PATH|/Users/yourname/Downloads/chicago_neighborhood_data|g' \
    load_data.sql > load_data_local.sql

# Windows (PowerShell):
(Get-Content load_data.sql) -replace '/REPLACE_WITH_YOUR_DATA_PATH', \
    'C:/Users/yourname/Downloads/chicago_neighborhood_data' | \
    Set-Content load_data_local.sql
```

This creates `load_data_local.sql` — a copy with the correct paths filled in.
The original `load_data.sql` is not changed.

**Verify it worked:**
```bash
grep REPLACE load_data_local.sql
# Should return nothing (no more placeholders)
```

---

## Step 4 — Enable LOCAL INFILE (one-time MySQL setting)

The load script uses `LOAD DATA LOCAL INFILE`. If your MySQL server has this disabled,
run this once as root in MySQL:

```sql
SET GLOBAL local_infile = 1;
```

Check if it's needed: if Step 5 gives `ERROR 1290 (HY000): The MySQL server is running
with the --secure-file-priv option`, run the command above and retry.

---

## Step 5 — Load all data (~15–25 minutes)

```bash
mysql -u root -p --local-infile=1 chicago_neighborhood < load_data_local.sql
```

The script will print progress and row counts as it loads each table.
The longest steps are `service_requests` (~7.7M rows) and `crime_records` (~1.5M rows).

---

## Step 6 — Verify row counts

Paste this into MySQL to confirm all tables loaded correctly:

```sql
USE chicago_neighborhood;
SELECT 'community_areas'             AS tbl, COUNT(*) AS rows FROM community_areas             UNION ALL
SELECT 'census_profiles'             AS tbl, COUNT(*) AS rows FROM census_profiles             UNION ALL
SELECT 'cta_rail_stations'           AS tbl, COUNT(*) AS rows FROM cta_rail_stations           UNION ALL
SELECT 'cta_lines'                   AS tbl, COUNT(*) AS rows FROM cta_lines                   UNION ALL
SELECT 'serves'                      AS tbl, COUNT(*) AS rows FROM serves                      UNION ALL
SELECT 'crime_records'               AS tbl, COUNT(*) AS rows FROM crime_records               UNION ALL
SELECT 'crime_aggregations'          AS tbl, COUNT(*) AS rows FROM crime_aggregations          UNION ALL
SELECT 'management_companies'        AS tbl, COUNT(*) AS rows FROM management_companies        UNION ALL
SELECT 'housing_units'               AS tbl, COUNT(*) AS rows FROM housing_units               UNION ALL
SELECT 'rail_ridership'              AS tbl, COUNT(*) AS rows FROM rail_ridership              UNION ALL
SELECT 'service_requests'            AS tbl, COUNT(*) AS rows FROM service_requests            UNION ALL
SELECT 'neighborhood_profiles'       AS tbl, COUNT(*) AS rows FROM neighborhood_profiles       UNION ALL
SELECT 'wards'                       AS tbl, COUNT(*) AS rows FROM wards                       UNION ALL
SELECT 'community_area_ward_overlap' AS tbl, COUNT(*) AS rows FROM community_area_ward_overlap;
```

Expected counts:

| Table | Expected rows |
|---|---:|
| `community_areas` | 77 |
| `census_profiles` | 77 |
| `cta_rail_stations` | 144 |
| `cta_lines` | 8 |
| `serves` | 191 |
| `crime_records` | 1,487,886 |
| `crime_aggregations` | 92,329 |
| `management_companies` | 236 |
| `housing_units` | 598 |
| `rail_ridership` | 127,674 |
| `service_requests` | 7,763,457 |
| `neighborhood_profiles` | 77 |
| `wards` | 50 |
| `community_area_ward_overlap` | 264 |

---

## Common Errors and Fixes

| Error | Cause | Fix |
|---|---|---|
| `ERROR 2 (HY000): File not found` | Wrong path in `load_data_local.sql` | Re-run the `sed` command with the correct path; check no trailing space |
| `ERROR 1290: --secure-file-priv` | LOCAL INFILE disabled | Run `SET GLOBAL local_infile = 1;` in MySQL, then re-run with `--local-infile=1` |
| `ERROR 1045: Access denied` | Wrong MySQL password | Check password; try `mysql -u root -p` interactively to confirm |
| `ERROR 1146: Table doesn't exist` | `schema.sql` not run first | Run `mysql -u root -p < schema.sql` before the load step |
| `mysql.server: command not found` (Mac) | MySQL not in PATH | Run `/usr/local/mysql/bin/mysql` or add `/usr/local/mysql/bin` to PATH |
| Load stops partway through | Large table timeout | Re-run the load — `INSERT IGNORE` means re-running will skip already-loaded rows safely |

---

## Data Notes for Queries and App Development

**`crime_records`** — Individual incidents 2020–2026 (1.49M rows). The primary type column
has ~30 categories. Use `crime_aggregations` for trend/ranking queries — it's much faster.

**`crime_aggregations`** — Monthly counts by neighborhood × year × crime type, covering
2020–2026. Use this for year-over-year analysis and neighborhood ranking queries.

**`service_requests`** — Individual 311 requests 2022–2026 (7.7M rows). `response_days`
is NOT stored — compute it at query time: `DATEDIFF(closed_date, created_date)`.

**`rail_ridership`** — One row per station × month × day_type. Day types: `W` (weekday),
`A` (Saturday), `U` (Sunday/holiday). These are AVERAGES for that day type, not totals.

**`housing_units`** — 598 individual affordable housing developments. Join to
`management_companies` on the `management_company` column for phone/contact info.

**`neighborhood_profiles`** — Pre-materialized 2024 summary per community area. Useful for
UI queries that need a fast single-row-per-neighborhood result without heavy aggregation.

**`census_profiles.transit_share_pct`** — Stored as a **decimal fraction (0–1), not a
percentage**. Example: `0.43` means 43% of commuters use public transit. Write queries as
`WHERE transit_share_pct > 0.30` (not `> 30`). Range in the data: 0.20–0.78.

**`community_area_ward_overlap`** — M:N table (second M:N in the schema). Maps the 77
community areas to the 50 city council wards with GIS-computed overlap percentages.

**`serves`** — M:N table (first M:N). Maps CTA rail stations to the lines that serve them
(e.g., a downtown station may be served by Red, Blue, and Green lines).

**Community area ID** — All tables join via `community_id` (integer 1–77). Community names
are in `community_areas.name` (title case, e.g., `Hyde Park`, `Lincoln Park`).

---

## Team Roles Reminder

| Member | Responsibility | Depends on |
|---|---|---|
| A (DB Architect) | Finalize and run `schema.sql` | Nothing |
| B (Data Pipeline) | Run `load_data_local.sql`, verify counts | A done |
| C (Query Developer) | Write and test queries | B done |
| D (GUI Developer) | Build/test the Python app | B done |
| E (QA + Docs) | Collect screenshots, finalize PDF | C done |
