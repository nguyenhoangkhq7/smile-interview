-- V13: Add raw_text columns to resumes and job_descriptions tables
-- This stores the pre-LLM raw PDF-extracted plain text for visual keyword highlighting.
-- The extracted_text column continues to hold the LLM-standardized Markdown used for vector search.

ALTER TABLE resumes
    ADD COLUMN IF NOT EXISTS raw_text TEXT;

ALTER TABLE job_descriptions
    ADD COLUMN IF NOT EXISTS raw_text TEXT;
