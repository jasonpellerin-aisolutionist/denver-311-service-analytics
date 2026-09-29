SET search_path TO denver311;

-- Partial index: every field-work query filters on is_field_request.
CREATE INDEX requests_field_type_year_idx
    ON requests (request_type, created_year) WHERE is_field_request;
CREATE INDEX requests_category_month_idx ON requests (request_category, created_month);
CREATE INDEX requests_channel_year_idx ON requests (channel, created_year);
CREATE INDEX requests_nbhd_idx ON requests (nbhd_id) WHERE nbhd_id IS NOT NULL;
CREATE INDEX requests_agency_year_idx ON requests (agency, created_year);

ANALYZE requests;
ANALYZE neighborhoods;
