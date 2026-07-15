-- V12: Optimize File Storage by moving from raw database bytea to Cloudinary URLs
ALTER TABLE resumes DROP COLUMN IF EXISTS file_content;
ALTER TABLE resumes ADD COLUMN IF NOT EXISTS file_url VARCHAR(500);
ALTER TABLE resumes ADD COLUMN IF NOT EXISTS cloudinary_id VARCHAR(255);

ALTER TABLE job_descriptions DROP COLUMN IF EXISTS file_content;
ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS file_url VARCHAR(500);
ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS cloudinary_id VARCHAR(255);
