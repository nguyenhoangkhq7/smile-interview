-- The interview practice system uses standard PostgreSQL and does not store
-- vector embeddings. Remove pgvector left behind by the legacy V3 migration.
DROP EXTENSION IF EXISTS vector;
