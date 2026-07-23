-- ============================================================
-- V3: Add pgvector extension and document_chunks table
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_chunks (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id       VARCHAR(128) NOT NULL,
    doc_type         VARCHAR(10) NOT NULL,        -- 'cv' | 'jd'
    parent_id        UUID,                        -- NULL for parent overview chunk
    chunk_type       VARCHAR(50) NOT NULL,        -- 'project_overview' | 'domain_child' | 'flat_section'
    domain           JSONB,                       -- e.g. ["security", "database"]
    content          TEXT NOT NULL,               -- Exact raw CV/JD content (used for Assessment & Grounding)
    enriched_content TEXT,                        -- Context-enriched content (used ONLY for embedding generation)
    embedding        VECTOR(1024),                -- Fixed 1024 dimensions for maximum speed
    created_at       TIMESTAMP DEFAULT NOW()
);

-- HNSW Vector Cosine index for fast 1024-dim similarity search
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- Simple Full-Text Search index (preserves tech keywords like JWT, Redis, AWS without English stemming)
CREATE INDEX IF NOT EXISTS idx_document_chunks_fts ON document_chunks USING gin (to_tsvector('simple', content));

-- Composite index for fast session filtering
CREATE INDEX IF NOT EXISTS idx_document_chunks_session_doc ON document_chunks(session_id, doc_type);
