"""Build data/processed/denver311.duckdb from the cleaned parquet, then run the quality checks."""

from __future__ import annotations

import os

import duckdb

from denver311 import DUCKDB_PATH, PROCESSED_DIR, ROOT, SQL_DIR


def run_file(con: duckdb.DuckDBPyConnection, name: str) -> None:
    print(f"-- {name}")
    con.execute((SQL_DIR / "duckdb" / name).read_text())


def main() -> None:
    os.chdir(ROOT)
    DUCKDB_PATH.unlink(missing_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH))
    run_file(con, "01_schema.sql")
    run_file(con, "02_quality_checks.sql")

    checks = con.execute("SELECT * FROM quality_checks").fetchall()
    for name, failing, tolerance, passed in checks:
        print(
            f"  [{'PASS' if passed else 'FAIL'}] {name}: {failing:,} failing (tolerance {tolerance:,})"
        )

    matched = con.execute(
        "SELECT COUNT(*) FILTER (WHERE nbhd_id IS NOT NULL), COUNT(*) FILTER (WHERE latitude IS NOT NULL) FROM requests"
    ).fetchone()
    print(f"  neighborhood match: {matched[0]:,} of {matched[1]:,} geocoded rows")

    enriched = PROCESSED_DIR / "requests_enriched.parquet"
    con.execute(f"COPY requests TO '{enriched}' (FORMAT parquet, COMPRESSION zstd)")
    con.execute(
        f"COPY (SELECT * EXCLUDE (geom) FROM neighborhoods) TO '{PROCESSED_DIR / 'neighborhoods.parquet'}' (FORMAT parquet)"
    )
    print(f"  wrote {enriched.name} and neighborhoods.parquet")
    con.close()

    if not all(row[3] for row in checks):
        raise SystemExit("quality checks failed")


if __name__ == "__main__":
    main()
