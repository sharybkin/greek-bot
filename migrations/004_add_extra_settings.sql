-- Migration: Add extra settings to users table
ALTER TABLE users ADD COLUMN personal_pronouns_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN possessive_pronouns_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN prepositions_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN interrogative_words_enabled BOOLEAN DEFAULT TRUE;
