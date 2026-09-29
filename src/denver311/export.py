"""Export aggregate tables for Tableau Public and Google Sheets (tableau/exports/).

Only aggregates leave the database: no addresses and no row-level records.
"""

from __future__ import annotations

import csv
import json
import os

import duckdb

from denver311 import DUCKDB_PATH, EXPORT_DIR, PROCESSED_DIR, ROOT

TABLES = {
    "yearly": "SELECT * FROM agg_yearly",
    "category_year": "SELECT * FROM agg_category_year",
    "monthly_category": "SELECT * FROM agg_monthly_category",
    "seasonality": "SELECT * FROM agg_seasonality",
    "hour_dow": "SELECT * FROM agg_hour_dow",
    "type_summary": "SELECT * FROM agg_type_summary",
    "type_year": "SELECT * FROM agg_type_year",
    "closure_integrity": "SELECT * FROM agg_closure_integrity",
    "published_los": "SELECT * FROM agg_published_los",
    "agency_year": "SELECT * FROM agg_agency_year",
    "open_backlog": "SELECT * FROM agg_open_backlog",
    "channel_year": "SELECT * FROM agg_channel_year",
    "type_channel_year": "SELECT * FROM agg_type_channel_year",
    "channel_speed": "SELECT * FROM agg_channel_speed",
    "deflection_candidates": "SELECT * FROM agg_deflection_candidates",
    "fcr_flag": "SELECT * FROM agg_fcr_flag",
    "neighborhood": "SELECT * FROM agg_neighborhood",
    "neighborhood_category": "SELECT * FROM agg_neighborhood_category",
    "council_district": "SELECT * FROM agg_council_district",
    "hotspots": "SELECT * FROM agg_hotspots",
    "quality_checks": "SELECT * FROM quality_checks",
}

KPI_SQL = """
WITH y AS (SELECT * FROM agg_yearly),
lfl AS (
    SELECT
        MAX(field_requests_like_for_like) FILTER (WHERE year = 2019) AS lfl_2019,
        MAX(field_requests_like_for_like) FILTER (WHERE year = 2025) AS lfl_2025
    FROM y
),
app AS (
    SELECT
        MAX(share_of_field) FILTER (WHERE year = 2022) AS app_2022,
        MAX(share_of_field) FILTER (WHERE year = 2019) AS app_2019,
        MAX(share_of_field) FILTER (WHERE year = 2025) AS app_2025
    FROM agg_channel_year WHERE channel = 'App (PocketGov)'
),
speed AS (
    SELECT COUNT(*) FILTER (WHERE app_minus_phone_hours > 0) AS slower, COUNT(*) AS compared
    FROM agg_channel_speed
),
gaps AS (
    SELECT COUNT(*) FILTER (WHERE record_gap) AS gaps, COUNT(*) AS type_years FROM agg_closure_integrity
),
nb AS (
    SELECT MIN(wait_index) AS lo, MAX(wait_index) AS hi FROM agg_neighborhood WHERE ranked_requests >= 500
),
cd AS (
    SELECT MIN(wait_index) AS lo, MAX(wait_index) AS hi FROM agg_council_district
),
defl AS (SELECT SUM(share_of_all_phone_contacts) AS top20_share FROM agg_deflection_candidates)
SELECT * FROM (VALUES
    ('Contacts, 2019-2025', (SELECT SUM(contacts) FROM y)::DOUBLE, 'count', 'Every row in the seven yearly files after cleaning.'),
    ('Field requests, 2019-2025', (SELECT SUM(field_requests) FROM y)::DOUBLE, 'count', 'Tied to a Denver place; not spam, duplicate, transferred, or out of jurisdiction.'),
    ('Field share of contacts', (SELECT SUM(field_requests) / SUM(contacts) FROM y), 'share', 'Most 311 contacts are questions, not field work.'),
    ('Closed within 15 minutes', (SELECT SUM(handled_on_contact) / SUM(contacts) FROM y), 'share', 'Contacts closed within 15 minutes of creation.'),
    ('Like-for-like field requests, 2019 to 2025', (SELECT lfl_2025 / lfl_2019 - 1 FROM lfl), 'change', 'Excludes solid-waste types, which leave the 311 file after 2020.'),
    ('App share of field requests, 2019', (SELECT app_2019 FROM app), 'share', 'PocketGov share of field requests.'),
    ('App share of field requests, 2022 peak', (SELECT app_2022 FROM app), 'share', 'PocketGov share of field requests.'),
    ('App share of field requests, 2025', (SELECT app_2025 FROM app), 'share', 'PocketGov share of field requests.'),
    ('Request types slower to close via app', (SELECT slower FROM speed)::DOUBLE, 'count', 'Out of ' || (SELECT compared FROM speed) || ' types with 500+ closed requests on both channels.'),
    ('Type-years with a record gap', (SELECT gaps FROM gaps)::DOUBLE, 'count', 'Out of ' || (SELECT type_years FROM gaps) || '; over 20% never closed or over 25% closed on one day.'),
    ('Top 20 answered-on-the-spot phone topics', (SELECT top20_share FROM defl), 'share', 'Share of all phone contacts: no location, answered, closed within 15 minutes.'),
    ('Neighborhood wait index, lowest', (SELECT lo FROM nb), 'index', '0.50 is typical for the same request type and year; 75 neighborhoods with 500+ ranked requests.'),
    ('Neighborhood wait index, highest', (SELECT hi FROM nb), 'index', '0.50 is typical for the same request type and year.'),
    ('Council district wait index, lowest', (SELECT lo FROM cd), 'index', 'All 11 districts.'),
    ('Council district wait index, highest', (SELECT hi FROM cd), 'index', 'All 11 districts.')
) AS t(metric, value, unit, note)
"""


def write_csv(con: duckdb.DuckDBPyConnection, name: str, query: str) -> int:
    path = EXPORT_DIR / f"{name}.csv"
    con.execute(f"COPY ({query}) TO '{path}' (HEADER, DELIMITER ',')")
    return con.execute(f"SELECT COUNT(*) FROM ({query})").fetchone()[0]


def main() -> None:
    os.chdir(ROOT)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    con.execute("LOAD spatial;")

    for name, query in TABLES.items():
        rows = write_csv(con, name, query)
        print(f"  {name}.csv: {rows:,} rows")
    rows = write_csv(con, "kpi_summary", KPI_SQL)
    print(f"  kpi_summary.csv: {rows} rows")

    geo = EXPORT_DIR / "neighborhoods_metrics.geojson"
    geo.unlink(missing_ok=True)
    con.execute(
        f"""
        COPY (
            SELECT a.* EXCLUDE (centroid_lat, centroid_lon), n.geom
            FROM agg_neighborhood a JOIN neighborhoods n USING (nbhd_id)
        ) TO '{geo}' WITH (FORMAT gdal, DRIVER 'GeoJSON')
        """
    )
    print(f"  {geo.name}: 78 polygons")
    con.close()

    log = json.loads((PROCESSED_DIR / "cleaning_log.json").read_text())
    with (EXPORT_DIR / "cleaning_log.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["step", "rows", "decision"])
        writer.writeheader()
        writer.writerows(log)
    print(f"  cleaning_log.csv: {len(log)} rows")


if __name__ == "__main__":
    main()
