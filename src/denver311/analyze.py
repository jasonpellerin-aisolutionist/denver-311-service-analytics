"""Run the analysis SQL (sql/duckdb/10-40) against the DuckDB database and print headline tables."""

from __future__ import annotations

import os

import duckdb

from denver311 import DUCKDB_PATH, ROOT, SQL_DIR

ANALYSIS_FILES = [
    "10_demand.sql",
    "20_resolution_time.sql",
    "25_published_los.sql",
    "30_channel_fcr.sql",
    "40_geography.sql",
]

PREVIEWS = {
    "agg_yearly": "SELECT * FROM agg_yearly",
    "agg_type_summary": """
        SELECT request_type, agency, requests_total, round(p50_days, 1) p50_d, round(p90_days, 1) p90_d,
               round(share_closed_within_1h, 3) lt1h, round(share_closed_after_30d, 3) gt30d,
               round(share_open_in_file, 3) open
        FROM agg_type_summary""",
    "benchmark trend (share within 2019 P90)": """
        PIVOT (SELECT request_type, year, round(share_within_2019_p90, 2) s FROM agg_type_year)
        ON year USING any_value(s) ORDER BY request_type""",
    "published LOS (share within DOTI goal)": """
        PIVOT (SELECT request_type || ' (' || los_business_days || ' bd)' AS type, year,
                      round(share_within_los, 2) s FROM agg_published_los)
        ON year USING any_value(s) ORDER BY type""",
    "agg_channel_year (field share)": """
        PIVOT (SELECT year, channel, round(share_of_field, 3) s FROM agg_channel_year)
        ON channel USING any_value(s) ORDER BY year""",
    "agg_channel_speed": "SELECT * FROM agg_channel_speed",
    "agg_deflection_candidates": "SELECT * FROM agg_deflection_candidates",
    "agg_council_district": "SELECT * FROM agg_council_district",
    "agg_neighborhood (slowest 10)": """
        SELECT neighborhood, population, field_requests, round(field_requests_per_1k_per_year, 1) per1k,
               round(wait_index, 3) wait_index, ranked_requests, per_capita_income, round(pct_poverty, 1) pov
        FROM agg_neighborhood ORDER BY wait_index DESC LIMIT 10""",
    "agg_neighborhood (fastest 10)": """
        SELECT neighborhood, population, field_requests, round(field_requests_per_1k_per_year, 1) per1k,
               round(wait_index, 3) wait_index, ranked_requests, per_capita_income, round(pct_poverty, 1) pov
        FROM agg_neighborhood WHERE ranked_requests >= 500 ORDER BY wait_index LIMIT 10""",
}


def main() -> None:
    os.chdir(ROOT)
    con = duckdb.connect(str(DUCKDB_PATH))
    con.execute("LOAD spatial;")
    for name in ANALYSIS_FILES:
        print(f"-- {name}")
        con.execute((SQL_DIR / "duckdb" / name).read_text())
    for title, query in PREVIEWS.items():
        print(f"\n== {title}")
        print(con.sql(query).df().to_string(index=False))
    con.close()


if __name__ == "__main__":
    main()
