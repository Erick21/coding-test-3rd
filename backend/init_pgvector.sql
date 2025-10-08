-- Initialize pgvector extension
-- This script is run automatically when the PostgreSQL container starts

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Grant permissions
GRANT ALL ON SCHEMA public TO funduser;

-- Info message
DO $$
BEGIN
  RAISE NOTICE 'pgvector extension initialized successfully';
END $$;

