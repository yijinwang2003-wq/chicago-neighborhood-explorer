# Chicago Neighborhood Explorer

An analytical MySQL database project for comparing Chicago's 77 community areas using demographics, affordability, city-supported affordable housing, crime, CTA rail access, rail ridership, 311 service response, and ward/community geography overlap.

## Stack

- MySQL 8.0
- Python
- Streamlit
- mysql-connector-python
- pandas, GeoPandas, Shapely

## Final Database Shape

Base tables:

```text
community_areas
census_profiles
management_companies
housing_developments
crime_records
cta_rail_stations
cta_lines
serves
rail_ridership_monthly
service_requests
wards
community_area_ward_overlap
```

Derived views:

```text
vw_crime_aggregation
vw_neighborhood_profile
vw_ward_community_profile
```

The two materialized M:N relationships are `serves` and `community_area_ward_overlap`. There is no `near_stop`, `housing_category`, `development_category`, `crime_aggregations`, or `neighborhood_profiles` base table.

## Setup

Install Python dependencies:

```bash
pip install -r requirements.txt
```

The loader reads MySQL settings from command-line flags or environment variables:

```bash
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3306
export MYSQL_USER=root
export MYSQL_PASSWORD=YOUR_PASSWORD
export MYSQL_DATABASE=chicago_neighborhood
```

`.env` is ignored by Git and should contain your real local credentials. Use
`.env.example` as the template for required variables.

## Run FastAPI Backend

Start the API server from the project root:

```bash
uvicorn api.main:app --reload
```

Then open the interactive API docs:

```text
http://127.0.0.1:8000/docs
```

The Phase 1 API uses the existing MySQL database, tables, and views. It does
not reload data or rerun ETL. The frontend reads through the API, with one POST
endpoint preserved for the existing service-request insert form.

The Streamlit frontend reads API settings from `API_BASE_URL`, defaulting to:

```text
http://localhost:8000
```

## Run App Containers With Docker Compose

This Compose setup containerizes only the application layer. It does not start
or manage MySQL. Your existing local MySQL instance must already contain the
schema, views, indexes, and Chicago datasets.

Create a local `.env` from `.env.example` and set the MySQL connection values
for your existing local database:

```bash
cp .env.example .env
```

When the API runs inside Docker, `localhost` means the API container itself. On
Docker Desktop, use this host value to reach MySQL running on your machine:

```text
MYSQL_HOST=host.docker.internal
```

The Streamlit container uses:

```text
API_BASE_URL=http://api:8000
```

Build and start all services:

```bash
docker compose up --build
```

If your Docker CLI only supports the legacy Compose command:

```bash
docker-compose up --build
```

Then verify:

```text
http://localhost:8000/docs
http://localhost:8501
```

Compose services:

```text
api       FastAPI backend on port 8000
frontend  Streamlit frontend on port 8501
```

The API connects to your existing MySQL database through `MYSQL_HOST`,
`MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE`. Docker
startup does not create a database, load data, or rerun ETL.

## Prepare Data

Generate MySQL-ready CSV files in `data/processed`:

```bash
python3 data/prepare_data.py
```

If the CMAP ArcGIS item changes, download the 2025 Community Data Snapshots CSV manually and pass it in:

```bash
python3 data/prepare_data.py --cmap-csv /path/to/CCA_2025.csv
```

The script downloads source extracts into `data/raw`, then prepares:

```text
community_areas.csv
wards.csv
community_area_ward_overlap.csv
census_profiles.csv
management_companies.csv
housing_developments.csv
crime_records.csv
cta_rail_stations.csv
cta_lines.csv
serves.csv
rail_ridership_monthly.csv
service_requests.csv
```

For CTA stations, the script uses polygon `covers` matching and leaves `community_id` NULL for stations outside Chicago community-area polygons. It does not use nearest-neighborhood fallback.

## Create and Load MySQL

Create schema, load data, views, and indexes:

```bash
python3 etl/load_database.py --create-schema --create-indexes
```

If you loaded data first and want to add indexes later without loading the CSV files again:

```bash
python3 etl/load_database.py --skip-load --create-indexes
```

To reload a database that already contains data, opt in explicitly:

```bash
python3 etl/load_database.py --truncate
```

Do not run the loader repeatedly without `--truncate`; the final tables use primary keys and unique keys, so duplicate rows should fail instead of being silently ignored.

## Validate

Run validation queries and save a report log:

```bash
python3 etl/validation.py
```

The output is written to:

```text
report_assets/row_count_log.txt
```

Key checks include 77 community areas, 50 wards, both directions of the ward/community M:N relationship, unique station-month ridership rows, and the count of `OPEN_DATA` versus `GUI_INPUT` service-request rows.

## Run Tests

The pytest suite mocks the FastAPI database dependency, so it does not require
a running MySQL server or loaded data.

```bash
pytest
```

The tests cover API health, neighborhood list/detail, compare responses,
invalid compare IDs, 404 cases, and response schema shape.

## Continuous Integration

GitHub Actions runs on every push and pull request:

```text
.github/workflows/ci.yml
```

The CI job checks out the repo, sets up Python, installs `requirements.txt`,
compiles Python files, and runs `pytest`. It does not require MySQL, Docker, or
any external service.

## Manual SQL Order

If you prefer MySQL Workbench or the MySQL CLI, run:

```bash
mysql -u root -p < sql/00_create_database.sql
mysql -u root -p chicago_neighborhood < sql/01_create_tables.sql
mysql -u root -p chicago_neighborhood < sql/02_create_views.sql
mysql -u root -p chicago_neighborhood < sql/03_create_indexes.sql
```

Load data with `etl/load_database.py`, because it handles NULL conversion, booleans, and `LOAD DATA LOCAL INFILE` column mappings for the processed CSV files.

Demo SQL for screenshots is in:

```text
sql/04_demo_queries.sql
```
