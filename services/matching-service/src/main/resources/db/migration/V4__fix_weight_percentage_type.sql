-- ============================================================
-- V4: Fix column type mismatch for weight_percentage
-- ============================================================
-- Hibernate 6 maps Java Double → PostgreSQL float8 (DOUBLE PRECISION).
-- V1 created the column as NUMERIC(5,2) which fails schema validation.
-- This script casts the existing column to DOUBLE PRECISION in-place.
-- ============================================================

ALTER TABLE category_criteria_mapping
    ALTER COLUMN weight_percentage TYPE DOUBLE PRECISION
        USING weight_percentage::DOUBLE PRECISION;
