-- Migration: Add premium fields to users table
-- Created: 2026-02-14

-- Add premium status field
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT FALSE;

-- Add daily generation tracking fields
ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_generation_count INT DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_generation_reset TIMESTAMP DEFAULT NOW();

-- Update existing users to have default values
UPDATE users 
SET is_premium = FALSE, 
    daily_generation_count = 0, 
    last_generation_reset = NOW()
WHERE is_premium IS NULL;
