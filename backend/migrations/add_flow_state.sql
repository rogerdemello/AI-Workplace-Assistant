-- Migration: add flow state to conversations
-- Run this against your Supabase database

ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS active_flow VARCHAR(100),
ADD COLUMN IF NOT EXISTS last_intent VARCHAR(100),
ADD COLUMN IF NOT EXISTS flow_data TEXT;

CREATE INDEX IF NOT EXISTS idx_conversations_active_flow ON conversations(active_flow);
CREATE INDEX IF NOT EXISTS idx_conversations_last_intent ON conversations(last_intent);
