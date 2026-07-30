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
      id UUID PRIMARY KEY,
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
      id UUID PRIMARY KEY,
      user_id UUID REFERENCES users(id) ON DELETE SET NULL,
      file_name VARCHAR(255) NOT NULL,
      parsed_content TEXT,
      raw_text TEXT,
      file_url VARCHAR(500),
      cloudinary_id VARCHAR(255),
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS job_descriptions (
      id UUID PRIMARY KEY,
      user_id UUID REFERENCES users(id) ON DELETE SET NULL,
      title VARCHAR(255) NOT NULL,
      parsed_content TEXT,
      raw_text TEXT,
      file_url VARCHAR(500),
      cloudinary_id VARCHAR(255),
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS resume_assessments (
      id UUID PRIMARY KEY,
      session_id VARCHAR(128) UNIQUE,
      job_category VARCHAR(50),
      seniority_level VARCHAR(20),
      overall_match_score INTEGER,
      eligibility VARCHAR(50),
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS evidence_items (
      id UUID PRIMARY KEY,
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
      id UUID PRIMARY KEY,
      assessment_id UUID NOT NULL REFERENCES resume_assessments(id) ON DELETE CASCADE,
      category VARCHAR(100),
      score INTEGER,
      max_score INTEGER,
      feedback TEXT,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS improvements (
      id UUID PRIMARY KEY,
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
      overall_score INTEGER,
      overall_feedback TEXT,
      user_rating INTEGER,
      user_feedback_text TEXT,
      started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      ended_at TIMESTAMP WITH TIME ZONE
    );

    CREATE TABLE IF NOT EXISTS session_questions (
      id UUID PRIMARY KEY,
      session_id VARCHAR(128) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
      question_config TEXT,
      candidate_context TEXT,
      total_questions INTEGER,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS questions (
      id UUID PRIMARY KEY,
      session_question_id UUID NOT NULL REFERENCES session_questions(id) ON DELETE CASCADE,
      category VARCHAR(100),
      question_text TEXT,
      expected_answer TEXT,
      difficulty_level INTEGER,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS session_metadata (
      id UUID PRIMARY KEY,
      session_question_id UUID NOT NULL REFERENCES session_questions(id) ON DELETE CASCADE,
      metadata_key VARCHAR(100),
      metadata_value TEXT
    );

    CREATE TABLE IF NOT EXISTS session_turns (
      id UUID PRIMARY KEY,
      session_id VARCHAR(128) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
      turn_number INTEGER NOT NULL,
      question_id UUID REFERENCES questions(id) ON DELETE SET NULL,
      dynamic_question_text TEXT,
      answer TEXT,
      score INTEGER,
      strengths TEXT,
      improvements TEXT,
      suggested_answer TEXT,
      topic_tag VARCHAR(100),
      is_deep_dive BOOLEAN DEFAULT FALSE,
      latency_ms INTEGER,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(session_id, turn_number)
    );
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
