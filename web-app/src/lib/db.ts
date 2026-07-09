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
  const createResumesTable = `
    CREATE TABLE IF NOT EXISTS resumes (
      id SERIAL PRIMARY KEY,
      user_id VARCHAR(255),
      file_name VARCHAR(255) NOT NULL,
      extracted_text TEXT,
      file_content BYTEA,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
  `;

  const createJdsTable = `
    CREATE TABLE IF NOT EXISTS job_descriptions (
      id SERIAL PRIMARY KEY,
      user_id VARCHAR(255),
      title VARCHAR(255) NOT NULL,
      extracted_text TEXT,
      file_content BYTEA,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
  `;

  const createSessionsTable = `
    CREATE TABLE IF NOT EXISTS sessions (
      id VARCHAR(255) PRIMARY KEY,
      date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      interview_type VARCHAR(50),
      role_title VARCHAR(255),
      cv_filename VARCHAR(255),
      jd_filename VARCHAR(255),
      overall_score INT,
      status VARCHAR(50),
      overall_feedback TEXT,
      competency_fit_score INT,
      technical_depth_score INT,
      match_level VARCHAR(50),
      candidate_level VARCHAR(50),
      role_type_detected VARCHAR(100),
      years_of_experience_estimate VARCHAR(50),
      strong_areas JSONB,
      gap_areas JSONB,
      critical_missing_skills JSONB,
      section_wise_feedback JSONB,
      actionable_suggestions JSONB
    );
  `;

  const createTurnsTable = `
    CREATE TABLE IF NOT EXISTS session_turns (
      id SERIAL PRIMARY KEY,
      session_id VARCHAR(255) REFERENCES sessions(id) ON DELETE CASCADE,
      question TEXT,
      answer TEXT,
      score INT,
      strengths TEXT,
      improvements TEXT,
      suggested_answer TEXT,
      topic_tag VARCHAR(100),
      is_deep_dive BOOLEAN
    );
  `;

  await pool.query(createResumesTable);
  await pool.query(createJdsTable);
  await pool.query(createSessionsTable);
  await pool.query(createTurnsTable);

  // Alter sessions to add resume_id, jd_id, and all assessment columns if they do not exist
  const alterColumns = [
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS resume_id INT REFERENCES resumes(id) ON DELETE SET NULL;',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS jd_id INT REFERENCES job_descriptions(id) ON DELETE SET NULL;',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS competency_fit_score INT;',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS technical_depth_score INT;',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS match_level VARCHAR(50);',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS candidate_level VARCHAR(50);',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS role_type_detected VARCHAR(100);',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS years_of_experience_estimate VARCHAR(50);',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS strong_areas JSONB;',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS gap_areas JSONB;',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS critical_missing_skills JSONB;',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS section_wise_feedback JSONB;',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS actionable_suggestions JSONB;',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS evidence_items JSONB;',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS additional_evidence_items JSONB;',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS score_breakdown JSONB;',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS top_priority_improvements JSONB;',
    'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS hiring_recommendation VARCHAR(50);'
  ];

  for (const sql of alterColumns) {
    await pool.query(sql);
  }

  console.log('[DB] Database tables initialized successfully');
}

export async function query(text: string, params?: any[]) {
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
