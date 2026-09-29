"""Denver 311 service request analytics."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DUCKDB_PATH = ROOT / "data" / "processed" / "denver311.duckdb"
SQL_DIR = ROOT / "sql"
EXPORT_DIR = ROOT / "tableau" / "exports"
FIGURES_DIR = ROOT / "reports" / "figures"
