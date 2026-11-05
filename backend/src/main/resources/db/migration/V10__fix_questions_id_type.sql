-- Migration: V10__fix_questions_id_type.sql
-- Fix data type mismatch between Java entity Question (String/VARCHAR(50)) and PostgreSQL table questions (UUID).

ALTER TABLE session_turns DROP CONSTRAINT IF EXISTS session_turns_question_id_fkey;

ALTER TABLE session_turns ALTER COLUMN question_id TYPE VARCHAR(50) USING question_id::varchar;

ALTER TABLE questions ALTER COLUMN id TYPE VARCHAR(50) USING id::varchar;

ALTER TABLE session_turns ADD CONSTRAINT session_turns_question_id_fkey FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE SET NULL;
