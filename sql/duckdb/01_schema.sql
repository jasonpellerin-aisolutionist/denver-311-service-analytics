-- Build the DuckDB analysis database from the cleaned parquet and neighborhood polygons.
-- Run from the project root: paths are relative to it.

INSTALL spatial;
LOAD spatial;

CREATE OR REPLACE TABLE neighborhoods AS
SELECT
    NBHD_ID::INTEGER                      AS nbhd_id,
    NBHD_NAME                             AS neighborhood,
    DIST_NUM::INTEGER                     AS council_district,
    Nmbr_Population::INTEGER              AS population,
    Nmbr_Households::INTEGER              AS households,
    Nmbr_PerCapitaIncome::INTEGER         AS per_capita_income,
    Pct_PopulationInPoverty               AS pct_poverty,
    Pct_OccupiedUnitsWithRenters          AS pct_renters,
    ST_Y(ST_Centroid(geom))               AS centroid_lat,
    ST_X(ST_Centroid(geom))               AS centroid_lon,
    geom
FROM ST_Read('data/raw/neighborhoods_acs_2019_2023.geojson');

CREATE OR REPLACE TABLE requests AS
SELECT * FROM read_parquet('data/processed/requests.parquet');

-- Point-in-polygon join. The source neighborhood column is empty in every year,
-- so neighborhood is derived from the request coordinates.
CREATE OR REPLACE TABLE request_neighborhood AS
SELECT r.request_id, n.nbhd_id, n.neighborhood
FROM requests r
JOIN neighborhoods n
  ON ST_Contains(n.geom, ST_Point(r.longitude, r.latitude))
WHERE r.latitude IS NOT NULL;

CREATE OR REPLACE TABLE requests AS
SELECT r.*, rn.nbhd_id, rn.neighborhood
FROM requests r
LEFT JOIN request_neighborhood rn USING (request_id);

DROP TABLE request_neighborhood;

-- The population every field-work metric is computed on.
CREATE OR REPLACE VIEW field_requests AS
SELECT * FROM requests WHERE is_field_request;

-- Closed field requests with a valid duration: the base for time-to-close percentiles.
CREATE OR REPLACE VIEW field_closed AS
SELECT * FROM field_requests WHERE is_closed AND hours_to_close IS NOT NULL;
