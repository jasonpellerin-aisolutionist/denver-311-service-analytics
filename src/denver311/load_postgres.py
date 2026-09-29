"""Load the enriched parquet into PostgreSQL, then build indexes and materialized views.

Schema DDL runs through psycopg. The bulk load uses DuckDB's postgres extension, which
streams rows with binary COPY, so 3M rows load in seconds without a CSV round trip.
"""

from __future__ import annotations

import argparse
import os
import time

import duckdb
import psycopg

from denver311 import PROCESSED_DIR, ROOT, SQL_DIR

PG_SQL = SQL_DIR / "postgres"


def run_sql(conn: psycopg.Connection, name: str) -> None:
    print(f"-- {name}")
    conn.execute((PG_SQL / name).read_text())
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="denver311")
    parser.add_argument("--host", default=os.environ.get("PGHOST", "localhost"))
    parser.add_argument("--user", default=os.environ.get("PGUSER", os.environ.get("USER")))
    args = parser.parse_args()
    os.chdir(ROOT)

    dsn = f"dbname={args.database} host={args.host} user={args.user}"
    with psycopg.connect(dsn) as conn:
        run_sql(conn, "01_schema.sql")

    start = time.perf_counter()
    duck = duckdb.connect()
    duck.execute("INSTALL postgres; LOAD postgres;")
    duck.execute(f"ATTACH '{dsn}' AS pg (TYPE postgres)")
    duck.execute(
        f"INSERT INTO pg.denver311.neighborhoods SELECT * FROM read_parquet('{PROCESSED_DIR / 'neighborhoods.parquet'}')"
    )
    columns = [
        row[0]
        for row in duck.execute(
            "SELECT column_name FROM pg.information_schema.columns "
            "WHERE table_schema = 'denver311' AND table_name = 'requests' ORDER BY ordinal_position"
        ).fetchall()
    ]
    col_list = ", ".join(columns)
    duck.execute(
        f"INSERT INTO pg.denver311.requests ({col_list}) "
        f"SELECT {col_list} FROM read_parquet('{PROCESSED_DIR / 'requests_enriched.parquet'}')"
    )
    duck.close()
    print(f"  bulk load: {time.perf_counter() - start:.1f}s")

    with psycopg.connect(dsn) as conn:
        run_sql(conn, "02_indexes.sql")
        run_sql(conn, "10_views.sql")
        rows = conn.execute(
            "SELECT COUNT(*), COUNT(*) FILTER (WHERE is_field_request) FROM denver311.requests"
        ).fetchone()
        views = conn.execute(
            "SELECT matviewname FROM pg_matviews WHERE schemaname = 'denver311' ORDER BY 1"
        ).fetchall()
    print(f"  requests: {rows[0]:,} rows, {rows[1]:,} field requests")
    print(f"  materialized views: {', '.join(v[0] for v in views)}")
    parity(dsn)


# Each pair must return identical rows (numbers rounded to 6 places) from both engines.
PARITY_CHECKS = {
    "yearly counts": (
        "SELECT year, contacts, field_requests, field_requests_like_for_like, handled_on_contact, open_in_file "
        "FROM agg_yearly ORDER BY year",
        "SELECT year, contacts, field_requests, field_requests_like_for_like, handled_on_contact, open_in_file "
        "FROM denver311.mv_yearly ORDER BY year",
    ),
    "type-year percentiles": (
        "SELECT request_type, year, requests, open_in_file, round(p50_hours, 6), round(p90_hours, 6), "
        "round(share_within_2019_p90, 6) FROM agg_type_year ORDER BY 1, 2",
        "SELECT request_type, year, requests, open_in_file, round(p50_hours::numeric, 6), "
        "round(p90_hours::numeric, 6), round(share_within_2019_p90::numeric, 6) "
        'FROM denver311.mv_type_year ORDER BY request_type COLLATE "C", year',
    ),
    "channel by year": (
        "SELECT year, channel, contacts, field_requests FROM agg_channel_year ORDER BY 1, 2",
        'SELECT year, channel, contacts, field_requests FROM denver311.mv_channel_year ORDER BY year, channel COLLATE "C"',
    ),
    "neighborhood wait index": (
        "SELECT nbhd_id, ranked_requests, round(wait_index, 6) FROM agg_neighborhood "
        "WHERE ranked_requests IS NOT NULL ORDER BY 1",
        "SELECT nbhd_id, ranked_requests, round(wait_index::numeric, 6) FROM denver311.mv_neighborhood_wait "
        "WHERE ranked_requests > 0 ORDER BY 1",
    ),
}


def normalize(rows: list[tuple]) -> list[tuple]:
    return [tuple(float(v) if hasattr(v, "is_finite") else v for v in row) for row in rows]


def parity(dsn: str) -> None:
    from denver311 import DUCKDB_PATH

    duck = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    failures = 0
    with psycopg.connect(dsn) as conn:
        for name, (duck_sql, pg_sql) in PARITY_CHECKS.items():
            left = normalize(duck.execute(duck_sql).fetchall())
            right = normalize(conn.execute(pg_sql).fetchall())
            ok = left == right
            failures += not ok
            print(f"  [{'PASS' if ok else 'FAIL'}] DuckDB = PostgreSQL: {name} ({len(left)} rows)")
    duck.close()
    if failures:
        raise SystemExit(f"{failures} parity check(s) failed")


if __name__ == "__main__":
    main()
