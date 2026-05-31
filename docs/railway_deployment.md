# Railway Deployment Guide

This repository is prepared for a manual Railway deployment with three moving parts:

- Railway MySQL for the analytics database
- FastAPI API service
- Streamlit frontend service

The deployment path does not rerun ETL. It uses a local MySQL export/import workflow so the existing schema, views, indexes, stored procedure, and `neighborhood_profile_snapshot` table move into Railway intact.

## 1. Create the Railway project

1. Push the repository to GitHub.
2. Create a new Railway project from that repository.
3. Add a Railway MySQL service to the project.

## 2. Export the local MySQL database

Before exporting, make sure your local database already contains the snapshot table and its data. If needed, refresh it once locally:

```bash
mysql -u root -p chicago_neighborhood < sql/05_create_profile_snapshot.sql
```

Export the database with tables, views, indexes, stored routines, triggers, events, and the snapshot data:

```bash
MYSQL_HOST=127.0.0.1 \
MYSQL_PORT=3306 \
MYSQL_USER=root \
MYSQL_PASSWORD=YOUR_PASSWORD \
./scripts/export_mysql_dump.sh
```

That script wraps a `mysqldump` command equivalent to:

```bash
mysqldump -u root -p \
  --databases chicago_neighborhood \
  --single-transaction \
  --skip-lock-tables \
  --routines \
  --triggers \
  --events \
  --default-character-set=utf8mb4 \
  --set-gtid-purged=OFF \
  > chicago_neighborhood_dump.sql
```

## Alternative Railway demo import from processed CSVs

If you do not have your local MySQL root password, or you want a lighter Railway demo database instead of a full dump, use the processed CSV files in `db-data/chicago_neighborhood_data/`.

This path does not require `mysqldump` or any local MySQL server. It creates the lightweight demo schema in [sql/06_create_demo_database.sql](../sql/06_create_demo_database.sql), loads the processed CSVs, synthesizes the small demo tables needed by the current API endpoints, materializes `neighborhood_profile_snapshot`, and verifies the result.

Run it against Railway MySQL with:

```bash
MYSQL_HOST=YOUR_RAILWAY_MYSQL_HOST \
MYSQL_PORT=YOUR_RAILWAY_MYSQL_PORT \
MYSQL_USER=YOUR_RAILWAY_MYSQL_USER \
MYSQL_PASSWORD=YOUR_RAILWAY_MYSQL_PASSWORD \
MYSQL_DATABASE=YOUR_RAILWAY_MYSQL_DATABASE \
python3 scripts/import_demo_csv_to_railway.py
```

## 3. Import into Railway MySQL

Copy the Railway MySQL credentials from the Railway dashboard. Use the exact values Railway provides for the database service:

- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`

Then import the dump:

```bash
MYSQL_HOST=YOUR_RAILWAY_MYSQL_HOST \
MYSQL_PORT=YOUR_RAILWAY_MYSQL_PORT \
MYSQL_USER=YOUR_RAILWAY_MYSQL_USER \
MYSQL_PASSWORD=YOUR_RAILWAY_MYSQL_PASSWORD \
./scripts/import_mysql_dump.sh chicago_neighborhood_dump.sql
```

If you prefer a one-liner, the equivalent import command is:

```bash
MYSQL_PWD=YOUR_RAILWAY_MYSQL_PASSWORD mysql \
  -h YOUR_RAILWAY_MYSQL_HOST \
  -P YOUR_RAILWAY_MYSQL_PORT \
  -u YOUR_RAILWAY_MYSQL_USER \
  < chicago_neighborhood_dump.sql
```

## 4. Deploy the API service

1. Add a new service from the same GitHub repository.
2. Set the config file path to `/railway.api.toml`.
3. Use `api/Dockerfile` as the build target.
4. Set the API environment variables from Railway MySQL:

```text
MYSQL_HOST
MYSQL_PORT
MYSQL_USER
MYSQL_PASSWORD
MYSQL_DATABASE
```

5. Deploy the service and generate a public Railway domain.

The API health endpoint should be available at:

```text
https://YOUR-API-SERVICE.up.railway.app/health
```

And interactive docs should be available at:

```text
https://YOUR-API-SERVICE.up.railway.app/docs
```

## 5. Deploy the frontend service

1. Add a second service from the same repository.
2. Set the config file path to `/railway.frontend.toml`.
3. Use `app/Dockerfile` as the build target.
4. Set the frontend environment variable:

```text
API_BASE_URL=https://YOUR-API-SERVICE.up.railway.app
```

5. Deploy the service and generate a public Railway domain.

The frontend should be available at:

```text
https://YOUR-FRONTEND-SERVICE.up.railway.app
```

## 6. Verification checklist

- `/health` returns `{"status":"ok",...}`
- `/api/neighborhoods` returns 77 rows
- `/api/compare?ids=1,2,3` returns the expected comparison payload
- `/docs` loads without errors
- the frontend page loads and can reach the API through `API_BASE_URL`
- `neighborhood_profile_snapshot` contains 77 rows

## Notes

- Keep the SQL dump out of version control. The repository `.gitignore` already ignores `*_dump.sql`.
- Do not rerun ETL during deployment. The dump/import path is the deployment mechanism.
- Keep the original analytical views in place. The snapshot table is an optimization layer, not a schema replacement.
