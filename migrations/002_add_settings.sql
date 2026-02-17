-- Add settings columns to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS plural_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS tense_restriction VARCHAR(20) DEFAULT 'all';
