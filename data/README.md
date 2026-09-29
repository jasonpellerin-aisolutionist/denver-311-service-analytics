# Data provenance

Raw and processed files are not committed. `make download` fetches the sources and writes
`data/raw/manifest.json` with byte counts, SHA-256 checksums, and timestamps.

## Sources

All from the City and County of Denver Open Data Catalog
(ArcGIS Hub: `https://opendata-geospatialdenver.hub.arcgis.com`), licensed under
[Creative Commons Attribution 3.0](https://creativecommons.org/licenses/by/3.0/)
(CC BY 3.0). Downloaded 2026-09-29.

| File | Hub item | Format published | Bytes | Rows after cleaning |
|---|---|---|---|---|
| `311_service_requests_2019.csv` | [acc3b988031749038b54c2fb8eedf320](https://opendata-geospatialdenver.hub.arcgis.com/datasets/acc3b988031749038b54c2fb8eedf320) | Feature Service export, UTF-8 with BOM | 83,824,288 | 432,443 |
| `311_service_requests_2020.csv` | [63678a1854b740fba4ccdb34f5857538](https://opendata-geospatialdenver.hub.arcgis.com/datasets/63678a1854b740fba4ccdb34f5857538) | Feature Service export, UTF-8 with BOM | 81,258,103 | 424,358 |
| `311_service_requests_2021.csv` | [7b1e415350424ed495b813874b02e88e](https://opendata-geospatialdenver.hub.arcgis.com/datasets/7b1e415350424ed495b813874b02e88e) | Feature Service export, UTF-8 with BOM | 67,342,016 | 352,623 |
| `311_service_requests_2022.csv` | [ef0a786fce784065918854d5b7eb28a7](https://opendata-geospatialdenver.hub.arcgis.com/datasets/ef0a786fce784065918854d5b7eb28a7) | Feature Service export, UTF-8 with BOM | 80,642,821 | 420,847 |
| `311_service_requests_2023.csv` | [ff6c84d8881647ca97b439971ad20a72](https://opendata-geospatialdenver.hub.arcgis.com/datasets/ff6c84d8881647ca97b439971ad20a72) | Feature Service export, UTF-8 with BOM | 90,510,430 | 474,562 |
| `311_service_requests_2024.csv` | [79f43c95bf9a4ac19ef8217c5367e6c4](https://opendata-geospatialdenver.hub.arcgis.com/datasets/79f43c95bf9a4ac19ef8217c5367e6c4) | CSV item, Windows-1252, quoted | 97,618,615 | 454,027 |
| `311_service_requests_2025.csv` | [5bdb9b3033d74782a4c410e548887ede](https://opendata-geospatialdenver.hub.arcgis.com/datasets/5bdb9b3033d74782a4c410e548887ede) | CSV item, Windows-1252, quoted | 97,490,714 | 451,470 |
| `neighborhoods_acs_2019_2023.geojson` | [9bd8a0dd46714e3a96c489b0f8dc3edb](https://opendata-geospatialdenver.hub.arcgis.com/datasets/9bd8a0dd46714e3a96c489b0f8dc3edb) | Feature Service query, GeoJSON (EPSG:4326) | 423,032 | 78 neighborhoods |

Total after cleaning: **3,010,330** contacts (2,015 exact duplicates removed). Line counts in the
raw files are higher than row counts because some quoted text fields contain line breaks.

## Reference

- DOTI Level of Service goals (business days): [Resident Level of Service for DOTI Requests](https://denvergov.org/Government/Agencies-Departments-Offices/Agencies-Departments-Offices-Directory/Department-of-Transportation-and-Infrastructure/Resident-Level-of-Service-for-DOTI-Requests),
  retrieved 2026-09-29. Used for Pothole (5), Signal Hazard (Traffic) (5), Transportation Signal
  Maintenance (30), Transportation Sign Maintenance (45), and Signal Timing (90).

## Files in this folder

- `data_dictionary.csv`: every column in the cleaned table, with type, source, and description.
- `raw/`: downloaded files (gitignored).
- `processed/`: `requests.parquet`, `requests_enriched.parquet`, `neighborhoods.parquet`,
  `cleaning_log.json`, `denver311.duckdb` (gitignored).

## Privacy

The source data excludes personal information. Only aggregates leave the database
(`tableau/exports/`, the workbook, and the figures); no addresses or row-level records are
published by this project.
