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
      skills_analysis JSONB,
      experience_evaluation TEXT,
      project_evaluation TEXT,
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

  await pool.query(createSessionsTable);
  await pool.query(createTurnsTable);
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
