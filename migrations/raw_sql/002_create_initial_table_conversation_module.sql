-- This migration script creates the initial tables for the conversation module
-- It includes tables for users, conversations, and messages
-- Ensure the pgcrypto extension is enabled for UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Conversations table to store user conversations
CREATE TABLE IF NOT EXISTS conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  title TEXT,
  summary TEXT,
  summary_embedding VECTOR(1536),
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_user_id_created_at
  ON conversations(user_id, created_at DESC);

CREATE INDEX idx_conversations_summary_embedding
  ON conversations USING ivfflat (summary_embedding);


-- Messages table to store individual messages in conversations
CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  sender_id UUID REFERENCES users(id),
  role VARCHAR(20) NOT NULL,               -- 'user', 'assistant', 'system', etc.
  model_id VARCHAR(50) NOT NULL DEFAULT 'gemini-2.0-flash',
  message TEXT NOT NULL,
  message_embedding VECTOR(1536),                  -- optional message embedding (for search)
  parent_message_id UUID REFERENCES messages(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation_created_at
  ON messages(conversation_id, created_at);

CREATE INDEX idx_messages_embedding
  ON messages USING ivfflat (message_embedding);