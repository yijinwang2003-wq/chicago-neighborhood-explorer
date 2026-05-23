# Chicago Neighborhood Explorer

An analytical database project for comparing Chicago's 77 Community Areas using demographics, affordability, affordable housing, crime, CTA rail access, rail ridership, and 311 service response data.

## Stack

- MySQL 8.0
- Python
- Streamlit
- mysql-connector-python

## Project Structure

```text
chicago-neighborhood-explorer/
|-- README.md
|-- requirements.txt
|-- sql/
|   |-- 00_create_database.sql
|   |-- 01_create_tables.sql
|   |-- 02_create_views.sql
|   `-- 03_create_indexes.sql
|-- etl/
|-- app/
|-- data/
|   |-- raw/
|   `-- processed/
|-- report_assets/
|   `-- screenshots/
`-- docs/
```

## Setup Notes

Create the MySQL database objects in this order:

```bash
mysql -u <user> -p < sql/00_create_database.sql
mysql -u <user> -p chicago_neighborhood_explorer < sql/01_create_tables.sql
mysql -u <user> -p chicago_neighborhood_explorer < sql/02_create_views.sql
mysql -u <user> -p chicago_neighborhood_explorer < sql/03_create_indexes.sql
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

The ETL scripts and Streamlit app will be added in later development steps.
