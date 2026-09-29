-- PostgreSQL 17 schema for the cleaned Denver 311 table.
-- Loaded by src/denver311/load_postgres.py; the analysis views live in 10_views.sql.

DROP SCHEMA IF EXISTS denver311 CASCADE;
CREATE SCHEMA denver311;
SET search_path TO denver311;

CREATE TABLE neighborhoods (
    nbhd_id            integer PRIMARY KEY,
    neighborhood       text    NOT NULL,
    council_district   smallint,
    population         integer NOT NULL,
    households         integer,
    per_capita_income  integer,
    pct_poverty        double precision,
    pct_renters        double precision,
    centroid_lat       double precision,
    centroid_lon       double precision
);

CREATE TABLE requests (
    request_id                  text PRIMARY KEY,
    file_year                   smallint    NOT NULL,
    created_at                  timestamp   NOT NULL,
    closed_at                   timestamp,
    created_date                date        NOT NULL,
    created_year                smallint    NOT NULL,
    created_month               timestamp   NOT NULL,
    created_hour                smallint    NOT NULL,
    created_dow                 smallint    NOT NULL,
    hours_to_close              double precision CHECK (hours_to_close >= 0),
    days_to_close               double precision,
    is_closed                   boolean     NOT NULL,
    flag_closed_before_created  boolean     NOT NULL,
    request_type                text        NOT NULL,
    request_category            text        NOT NULL,
    agency                      text        NOT NULL,
    case_status                 text,
    status_group                text        NOT NULL,
    case_source                 text,
    channel                     text        NOT NULL,
    first_call_resolution       boolean,
    has_location                boolean     NOT NULL,
    is_field_request            boolean     NOT NULL,
    incident_address_1          text,
    incident_address_2          text,
    incident_intersection_1     text,
    incident_intersection_2     text,
    incident_zip                char(5),
    customer_zip                char(5),
    latitude                    double precision,
    longitude                   double precision,
    council_district            smallint CHECK (council_district BETWEEN 1 AND 11),
    police_district             smallint CHECK (police_district BETWEEN 1 AND 7),
    case_summary                text,
    nbhd_id                     integer REFERENCES neighborhoods (nbhd_id),
    neighborhood                text
);

COMMENT ON TABLE requests IS 'Denver 311 service requests 2019-2025, cleaned. Source: Denver Open Data Catalog (CC BY 3.0).';
COMMENT ON COLUMN requests.is_field_request IS 'Tied to a Denver place and not invalid, transferred out, or out of jurisdiction.';
COMMENT ON COLUMN requests.hours_to_close IS 'Hours from 311 case creation to 311 case closure. Measures the case record, not crew completion.';
COMMENT ON COLUMN requests.neighborhood IS 'Derived by point-in-polygon join to the 78 statistical neighborhoods; the source column is empty.';
