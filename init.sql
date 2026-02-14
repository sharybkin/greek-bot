-- Greek Learning Bot Database Schema
-- PostgreSQL 16+

-- Таблица уроков
CREATE TABLE IF NOT EXISTS lessons (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    order_number INT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Таблица слов
CREATE TABLE IF NOT EXISTS words (
    id SERIAL PRIMARY KEY,
    greek_word VARCHAR(200) NOT NULL,
    russian_translation VARCHAR(300) NOT NULL,
    word_type VARCHAR(50),
    lesson_id INT REFERENCES lessons(id) ON DELETE CASCADE,
    usage_example_greek TEXT,
    usage_example_russian TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_words_lesson ON words(lesson_id);

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    telegram_id BIGINT PRIMARY KEY,
    username VARCHAR(100),
    first_name VARCHAR(100),
    current_lesson_id INT REFERENCES lessons(id) ON DELETE SET NULL,
    selected_lessons JSONB DEFAULT '[]'::jsonb,  -- Массив ID выбранных уроков
    difficulty_level INT DEFAULT 1 CHECK (difficulty_level BETWEEN 1 AND 3),
    is_premium BOOLEAN DEFAULT FALSE,  -- Premium статус пользователя
    daily_generation_count INT DEFAULT 0,  -- Количество генераций за сегодня
    last_generation_reset TIMESTAMP DEFAULT NOW(),  -- Последний сброс счетчика
    created_at TIMESTAMP DEFAULT NOW(),
    last_active_at TIMESTAMP DEFAULT NOW()
);

-- Таблица слов для повторения
CREATE TABLE IF NOT EXISTS review_words (
    id SERIAL PRIMARY KEY,
    user_telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    word_id INT REFERENCES words(id) ON DELETE CASCADE,
    added_at TIMESTAMP DEFAULT NOW(),
    review_count INT DEFAULT 0,
    last_reviewed_at TIMESTAMP,
    next_review_at TIMESTAMP,
    mastered BOOLEAN DEFAULT FALSE,
    UNIQUE(user_telegram_id, word_id)
);

CREATE INDEX idx_review_next ON review_words(user_telegram_id, next_review_at);
CREATE INDEX idx_user_word_unique ON review_words(user_telegram_id, word_id);

-- Таблица истории предложений
CREATE TABLE IF NOT EXISTS sentence_history (
    id SERIAL PRIMARY KEY,
    user_telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    greek_sentence TEXT NOT NULL,
    russian_translation TEXT NOT NULL,
    audio_file_id VARCHAR(200),
    difficulty_level INT,
    word_ids INT[],
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sentence_user ON sentence_history(user_telegram_id, created_at DESC);

-- Таблица статистики пользователей
CREATE TABLE IF NOT EXISTS user_statistics (
    id SERIAL PRIMARY KEY,
    user_telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    sentences_practiced INT DEFAULT 0,
    words_reviewed INT DEFAULT 0,
    new_words_learned INT DEFAULT 0,
    practice_time_minutes INT DEFAULT 0,
    UNIQUE(user_telegram_id, date)
);

CREATE INDEX idx_user_date ON user_statistics(user_telegram_id, date);
