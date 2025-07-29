CREATE TABLE IF NOT EXISTS memory_entries (
  id             UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID           NOT NULL REFERENCES users(id),
  created_at     TIMESTAMPTZ    NOT NULL DEFAULT now(),
  memory_type    TEXT           NOT NULL,
  content        TEXT           NOT NULL,
  meta_info       JSONB          NOT NULL DEFAULT '{}',
  embedding      VECTOR(1536),
  is_active      BOOLEAN        NOT NULL DEFAULT TRUE,
  evicted_at     TIMESTAMPTZ    NULL
);

-- Indexes for fast lookups
--  a) Find recent memories per user
CREATE INDEX idx_memory_agent_created 
  ON memory_entries(user_id, created_at DESC);

--  b) Filter to only “active” memories
CREATE INDEX idx_memory_agent_active 
  ON memory_entries(user_id, is_active)
  WHERE is_active;

--  c) JSONB meta_info queries
CREATE INDEX idx_memory_meta_info_gin
  ON memory_entries USING GIN (meta_info);

--  d) Vector similarity search (IVF–PQ or HNSW)
--    you’ll need to tune parameters per pgvector docs
CREATE INDEX idx_memory_embedding 
  ON memory_entries 
  USING ivfflat (embedding)
  WITH (lists = 100);

-- A table to record eviction/summarization history
CREATE TABLE IF NOT EXISTS memory_audit_log (
  log_id         BIGSERIAL     PRIMARY KEY,
  entry_id       UUID          NOT NULL REFERENCES memory_entries(id),
  action         TEXT          NOT NULL   -- e.g. 'evicted','summarized'
    CHECK (action IN ('evicted','summarized','updated')),
  detail         JSONB         DEFAULT '{}',
  action_time    TIMESTAMPTZ   NOT NULL DEFAULT now()
);