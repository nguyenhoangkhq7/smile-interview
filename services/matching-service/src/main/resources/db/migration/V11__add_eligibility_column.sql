-- Add eligibility column to resume_assessments
ALTER TABLE resume_assessments ADD COLUMN IF NOT EXISTS eligibility JSONB;

COMMENT ON COLUMN resume_assessments.eligibility IS 'JSONB block containing overall eligibility status and GATE requirements checks (YOE, Education, GPA)';
