PG_BIN ?= /opt/homebrew/opt/postgresql@17/bin
PGDATABASE ?= denver311
YEARS ?= 2019 2020 2021 2022 2023 2024 2025

.PHONY: setup download clean load-duckdb load-postgres analyze export workbook tableau notebooks lab lint all

setup:
	uv sync
	$(PG_BIN)/createdb $(PGDATABASE) 2>/dev/null || true

download:
	uv run python -m denver311.download --years $(YEARS)

clean:
	uv run python -m denver311.clean

load-duckdb:
	uv run python -m denver311.load_duckdb

load-postgres:
	uv run python -m denver311.load_postgres --database $(PGDATABASE)

analyze:
	uv run python -m denver311.analyze

export:
	uv run python -m denver311.export

workbook:
	uv run python -m denver311.workbook

tableau:
	uv run python -m denver311.tableau_workbook --install-palettes

notebooks:
	for nb in notebooks/*.ipynb; do uv run jupyter nbconvert --to notebook --execute --inplace $$nb; done

lab:
	uv run jupyter lab notebooks/

lint:
	uv run ruff check src
	uv run ruff format --check src

all: download clean load-duckdb load-postgres analyze export
