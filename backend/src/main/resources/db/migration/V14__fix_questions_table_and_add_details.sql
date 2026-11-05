-- Migration: V14__fix_questions_table_and_add_details.sql
-- Add missing columns to questions table to match Java entity Question and persist rich question attributes.

ALTER TABLE questions ADD COLUMN IF NOT EXISTS question_type VARCHAR(100);
ALTER TABLE questions ADD COLUMN IF NOT EXISTS expected_competency VARCHAR(200);
ALTER TABLE questions ADD COLUMN IF NOT EXISTS difficulty VARCHAR(50);
ALTER TABLE questions ADD COLUMN IF NOT EXISTS topic VARCHAR(150);
ALTER TABLE questions ADD COLUMN IF NOT EXISTS details TEXT;
