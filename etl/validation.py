#!/usr/bin/env python3
"""Run final-project validation queries and save a row-count log."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import mysql.connector


DEFAULT_DATABASE = "chicago_neighborhood_explorer"
DEFAULT_PASSWORD = os.getenv("MYSQL_PASSWORD", "YOUR_PASSWORD")

CHECKS = [
    (
        "community_count",
        "SELECT COUNT(*) AS community_count FROM community_areas",
    ),
    (
        "ward_count",
        "SELECT COUNT(*) AS ward_count FROM wards",
    ),
    (
        "profile_count",
        "SELECT COUNT(*) AS profile_count FROM census_profiles",
    ),
    (
        "neighborhood_profile_view_count",
        "SELECT COUNT(*) AS profile_view_count FROM vw_neighborhood_profile",
    ),
    (
        "community_to_multiple_wards",
        """
        SELECT community_id, COUNT(DISTINCT ward_id) AS ward_count
        FROM community_area_ward_overlap
        GROUP BY community_id
        HAVING COUNT(DISTINCT ward_id) > 1
        ORDER BY ward_count DESC, community_id
        LIMIT 10
        """,
    ),
    (
        "ward_to_multiple_communities",
        """
        SELECT ward_id, COUNT(DISTINCT community_id) AS community_count
        FROM community_area_ward_overlap
        GROUP BY ward_id
        HAVING COUNT(DISTINCT community_id) > 1
        ORDER BY community_count DESC, ward_id
        LIMIT 10
        """,
    ),
    (
        "station_mapping_summary",
        """
        SELECT
            COUNT(*) AS station_count,
            SUM(community_id IS NULL) AS stations_outside_chicago_scope
        FROM cta_rail_stations
        """,
    ),
    (
        "ridership_duplicate_check",
        """
        SELECT station_id, month_beginning, COUNT(*) AS row_count
        FROM rail_ridership_monthly
        GROUP BY station_id, month_beginning
        HAVING COUNT(*) > 1
        LIMIT 10
        """,
    ),
    (
        "service_request_sources",
        "SELECT record_source, COUNT(*) AS row_count FROM service_requests GROUP BY record_source",
    ),
    (
        "table_counts",
        """
        SELECT 'community_areas' AS table_name, COUNT(*) AS row_count FROM community_areas UNION ALL
        SELECT 'wards', COUNT(*) FROM wards UNION ALL
        SELECT 'community_area_ward_overlap', COUNT(*) FROM community_area_ward_overlap UNION ALL
        SELECT 'census_profiles', COUNT(*) FROM census_profiles UNION ALL
        SELECT 'management_companies', COUNT(*) FROM management_companies UNION ALL
        SELECT 'housing_developments', COUNT(*) FROM housing_developments UNION ALL
        SELECT 'crime_records', COUNT(*) FROM crime_records UNION ALL
        SELECT 'cta_rail_stations', COUNT(*) FROM cta_rail_stations UNION ALL
        SELECT 'cta_lines', COUNT(*) FROM cta_lines UNION ALL
        SELECT 'serves', COUNT(*) FROM serves UNION ALL
        SELECT 'rail_ridership_monthly', COUNT(*) FROM rail_ridership_monthly UNION ALL
        SELECT 'service_requests', COUNT(*) FROM service_requests
        ORDER BY table_name
        """,
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("MYSQL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MYSQL_PORT", "3306")))
    parser.add_argument("--user", default=os.getenv("MYSQL_USER", "root"))
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--database", default=os.getenv("MYSQL_DATABASE", DEFAULT_DATABASE))
    parser.add_argument("--output", type=Path, default=Path("report_assets/row_count_log.txt"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    connection = mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
    )
    cursor = connection.cursor()
    lines: list[str] = []
    for name, query in CHECKS:
        lines.append(f"## {name}")
        cursor.execute(query)
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        lines.append(",".join(columns))
        if rows:
            for row in rows:
                lines.append(",".join("" if value is None else str(value) for value in row))
        else:
            lines.append("(no rows)")
        lines.append("")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines))
    print(f"wrote {args.output}")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
