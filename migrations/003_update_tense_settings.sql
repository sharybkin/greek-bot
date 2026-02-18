-- Change tense_restriction to JSONB
ALTER TABLE users 
ALTER COLUMN tense_restriction TYPE JSONB 
USING CASE 
    WHEN tense_restriction = 'all' THEN '["present", "past", "future"]'::jsonb
    WHEN tense_restriction = 'present' THEN '["present"]'::jsonb
    WHEN tense_restriction = 'past' THEN '["past"]'::jsonb
    WHEN tense_restriction = 'future' THEN '["future"]'::jsonb
    ELSE '["present", "past", "future"]'::jsonb
END;

-- Set default
ALTER TABLE users ALTER COLUMN tense_restriction SET DEFAULT '["present", "past", "future"]'::jsonb;
