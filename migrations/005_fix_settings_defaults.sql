-- Migration to fix settings defaults and ensures no nulls
UPDATE users 
SET 
    plural_enabled = COALESCE(plural_enabled, TRUE),
    tense_restriction = COALESCE(tense_restriction, '["present", "past", "future"]'::jsonb),
    personal_pronouns_enabled = COALESCE(personal_pronouns_enabled, TRUE),
    possessive_pronouns_enabled = COALESCE(possessive_pronouns_enabled, TRUE),
    prepositions_enabled = COALESCE(prepositions_enabled, TRUE),
    interrogative_words_enabled = COALESCE(interrogative_words_enabled, TRUE);

-- Ensure defaults for future rows are set correctly if not already
ALTER TABLE users ALTER COLUMN plural_enabled SET DEFAULT TRUE;
ALTER TABLE users ALTER COLUMN tense_restriction SET DEFAULT '["present", "past", "future"]'::jsonb;
ALTER TABLE users ALTER COLUMN personal_pronouns_enabled SET DEFAULT TRUE;
ALTER TABLE users ALTER COLUMN possessive_pronouns_enabled SET DEFAULT TRUE;
ALTER TABLE users ALTER COLUMN prepositions_enabled SET DEFAULT TRUE;
ALTER TABLE users ALTER COLUMN interrogative_words_enabled SET DEFAULT TRUE;
