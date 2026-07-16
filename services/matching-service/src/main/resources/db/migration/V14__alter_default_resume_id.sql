-- V14: Alter default_resume_id in users table from UUID to VARCHAR(255)
-- This allows storing the serial integer resume ID as a string representation.

ALTER TABLE users 
    ALTER COLUMN default_resume_id TYPE VARCHAR(255) USING default_resume_id::varchar;
