-- Add system prompt cache fields to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS system_prompt TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS system_prompt_updated_at TIMESTAMP;
