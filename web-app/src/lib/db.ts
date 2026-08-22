import { Pool } from 'pg';

const getPoolConfig = () => {
  const host = process.env.POSTGRES_HOST || 'localhost';
  const port = parseInt(process.env.POSTGRES_PORT || '5432', 10);
  const user = process.env.POSTGRES_USER || 'postgres';
  const password = process.env.POSTGRES_PASSWORD || 'postgres';
  const database = process.env.POSTGRES_DB || 'smile_interview_db';

  return { host, port, user, password, database };
};

// Next.js hot-reload singleton pattern
const globalWithPool = globalThis as typeof globalThis & {
  postgresPool?: Pool;
};

if (!globalWithPool.postgresPool) {
  const config = getPoolConfig();
  console.log(`[DB] Creating new PostgreSQL Connection Pool to ${config.host}:${config.port}/${config.database}`);
  globalWithPool.postgresPool = new Pool({
    ...config,
    max: 10,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 2000,
  });
}

const pool = globalWithPool.postgresPool;

let dbInitialized = false;

export async function initDb() {
  const createTablesSql = `
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

    CREATE TABLE IF NOT EXISTS users (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      username VARCHAR(255) NOT NULL,
      email VARCHAR(255) NOT NULL UNIQUE,
      password_hash VARCHAR(255) NOT NULL,
      role VARCHAR(50) NOT NULL,
      phone_number VARCHAR(50),
      avatar_url VARCHAR(255),
      default_resume_id UUID,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS resumes (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id UUID REFERENCES users(id) ON DELETE SET NULL,
      file_name VARCHAR(255) NOT NULL,
      parsed_content TEXT,
      raw_text TEXT,
      extracted_text TEXT,
      file_url VARCHAR(500),
      cloudinary_id VARCHAR(255),
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    ALTER TABLE resumes ALTER COLUMN id SET DEFAULT gen_random_uuid();
    ALTER TABLE resumes ADD COLUMN IF NOT EXISTS extracted_text TEXT;

    CREATE TABLE IF NOT EXISTS job_descriptions (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id UUID REFERENCES users(id) ON DELETE SET NULL,
      title VARCHAR(255) NOT NULL,
      parsed_content TEXT,
      raw_text TEXT,
      extracted_text TEXT,
      file_url VARCHAR(500),
      cloudinary_id VARCHAR(255),
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    ALTER TABLE job_descriptions ALTER COLUMN id SET DEFAULT gen_random_uuid();
    ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS extracted_text TEXT;

    CREATE TABLE IF NOT EXISTS resume_assessments (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      session_id VARCHAR(128) UNIQUE,
      job_category VARCHAR(50),
      seniority_level VARCHAR(20),
      overall_match_score INTEGER,
      eligibility VARCHAR(50),
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS evidence_items (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      assessment_id UUID NOT NULL REFERENCES resume_assessments(id) ON DELETE CASCADE,
      criteria_id INTEGER,
      criteria_name VARCHAR(255),
      importance VARCHAR(50),
      jd_requirement TEXT,
      cv_evidence TEXT,
      status VARCHAR(50),
      reasoning TEXT,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS score_breakdowns (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      assessment_id UUID NOT NULL REFERENCES resume_assessments(id) ON DELETE CASCADE,
      category VARCHAR(100),
      score INTEGER,
      max_score INTEGER,
      feedback TEXT,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS improvements (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      assessment_id UUID NOT NULL REFERENCES resume_assessments(id) ON DELETE CASCADE,
      priority_rank INTEGER,
      topic VARCHAR(255),
      suggestion_details TEXT,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS sessions (
      id VARCHAR(128) PRIMARY KEY,
      user_id UUID REFERENCES users(id) ON DELETE SET NULL,
      resume_id UUID REFERENCES resumes(id) ON DELETE SET NULL,
      jd_id UUID REFERENCES job_descriptions(id) ON DELETE SET NULL,
      assessment_id UUID REFERENCES resume_assessments(id) ON DELETE SET NULL,
      status VARCHAR(50),
      interview_type VARCHAR(50),
      role_title VARCHAR(255),
      cv_filename VARCHAR(255),
      jd_filename VARCHAR(255),
      date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      overall_score INTEGER,
      overall_feedback TEXT,
      competency_fit_score INTEGER,
      technical_depth_score INTEGER,
      match_level VARCHAR(50),
      candidate_level VARCHAR(50),
      role_type_detected VARCHAR(100),
      years_of_experience_estimate VARCHAR(50),
      strong_areas TEXT,
      gap_areas TEXT,
      critical_missing_skills TEXT,
      section_wise_feedback TEXT,
      actionable_suggestions TEXT,
      evidence_items TEXT,
      additional_evidence_items TEXT,
      score_breakdown TEXT,
      top_priority_improvements TEXT,
      hiring_recommendation VARCHAR(255),
      eligibility TEXT,
      gate_evidence_items TEXT,
      must_have_evidence_items TEXT,
      prefer_to_have_evidence_items TEXT,
      user_rating INTEGER,
      user_feedback_text TEXT,
      started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      ended_at TIMESTAMP WITH TIME ZONE
    );

    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS cv_filename VARCHAR(255);
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS jd_filename VARCHAR(255);
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS competency_fit_score INTEGER;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS technical_depth_score INTEGER;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS match_level VARCHAR(50);
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS candidate_level VARCHAR(50);
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS role_type_detected VARCHAR(100);
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS years_of_experience_estimate VARCHAR(50);
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS strong_areas TEXT;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS gap_areas TEXT;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS critical_missing_skills TEXT;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS section_wise_feedback TEXT;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS actionable_suggestions TEXT;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS evidence_items TEXT;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS additional_evidence_items TEXT;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS score_breakdown TEXT;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS top_priority_improvements TEXT;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS hiring_recommendation VARCHAR(255);
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS eligibility TEXT;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS gate_evidence_items TEXT;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS must_have_evidence_items TEXT;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS prefer_to_have_evidence_items TEXT;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS quick_wins TEXT;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS skill_gaps TEXT;
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS current_stage VARCHAR(50) DEFAULT 'CV_JD_MATCHED';
    CREATE INDEX IF NOT EXISTS idx_sessions_current_stage ON sessions(current_stage);
    CREATE INDEX IF NOT EXISTS idx_evidence_items_assessment_id ON evidence_items(assessment_id);
    CREATE INDEX IF NOT EXISTS idx_score_breakdowns_assessment_id ON score_breakdowns(assessment_id);
    CREATE INDEX IF NOT EXISTS idx_improvements_assessment_id ON improvements(assessment_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_resume_jd ON sessions(resume_id, jd_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);

    CREATE TABLE IF NOT EXISTS session_questions (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      session_id VARCHAR(128) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
      question_config TEXT,
      candidate_context TEXT,
      total_questions INTEGER,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS questions (
      id VARCHAR(50) PRIMARY KEY,
      session_question_id UUID NOT NULL REFERENCES session_questions(id) ON DELETE CASCADE,
      category VARCHAR(100),
      question_text TEXT,
      expected_answer TEXT,
      difficulty_level INTEGER,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS session_metadata (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      session_question_id UUID NOT NULL REFERENCES session_questions(id) ON DELETE CASCADE,
      metadata_key VARCHAR(100),
      metadata_value TEXT
    );

    CREATE TABLE IF NOT EXISTS session_turns (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      session_id VARCHAR(128) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
      turn_number INTEGER,
      question_id VARCHAR(50) REFERENCES questions(id) ON DELETE SET NULL,
      question TEXT,
      dynamic_question_text TEXT,
      answer TEXT,
      score INTEGER,
      strengths TEXT,
      improvements TEXT,
      suggested_answer TEXT,
      topic_tag VARCHAR(100),
      is_deep_dive BOOLEAN DEFAULT FALSE,
      good_answer_signals TEXT,
      latency_ms INTEGER,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    ALTER TABLE session_turns ALTER COLUMN id SET DEFAULT gen_random_uuid();
    ALTER TABLE session_turns ALTER COLUMN turn_number DROP NOT NULL;
    ALTER TABLE session_turns ADD COLUMN IF NOT EXISTS question TEXT;
    ALTER TABLE session_turns ADD COLUMN IF NOT EXISTS good_answer_signals TEXT;
    ALTER TABLE session_turns ADD COLUMN IF NOT EXISTS hr_rating INTEGER;
    ALTER TABLE session_turns ADD COLUMN IF NOT EXISTS hr_feedback TEXT;

    ALTER TABLE session_turns DROP CONSTRAINT IF EXISTS session_turns_question_id_fkey;
    ALTER TABLE session_turns ALTER COLUMN question_id TYPE VARCHAR(50) USING question_id::varchar;
    ALTER TABLE questions ALTER COLUMN id TYPE VARCHAR(50) USING id::varchar;
    ALTER TABLE session_turns ADD CONSTRAINT session_turns_question_id_fkey FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE SET NULL;
  `;

  await pool.query(createTablesSql);
  console.log('[DB] Database tables initialized successfully');
}

export async function query(text: string, params?: unknown[]) {
  if (!dbInitialized) {
    try {
      await initDb();
      dbInitialized = true;
    } catch (err) {
      console.error('[DB] Failed to initialize database tables:', err);
    }
  }
  return pool.query(text, params);
}

export default pool;
