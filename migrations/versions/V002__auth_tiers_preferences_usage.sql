-- V002: Auth, tiers, preferences and usage
-- Adds auth fields to users table.
-- Creates user_tiers, user_preferences and usage tables.

ALTER TABLE users
    ADD COLUMN email         VARCHAR(255) UNIQUE NOT NULL DEFAULT '',
    ADD COLUMN password_hash VARCHAR(255) NOT NULL DEFAULT '';

-- Remove the defaults now that columns exist
ALTER TABLE users
    ALTER COLUMN email         DROP DEFAULT,
    ALTER COLUMN password_hash DROP DEFAULT;

-- Index on email for fast login lookups
CREATE INDEX IF NOT EXISTS idx_users_email
    ON users(email);


CREATE TABLE IF NOT EXISTS user_tiers (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tier                VARCHAR(50) NOT NULL DEFAULT 'free'
                            CHECK (tier IN ('free', 'pro', 'admin')),
    allowed_models      TEXT[] NOT NULL DEFAULT ARRAY[
                            'llama-3.3-70b-versatile',
                            'gemini-2.0-flash'
                        ],
    max_requests_per_day INTEGER NOT NULL DEFAULT 50,
    max_tokens_per_day   INTEGER NOT NULL DEFAULT 100000,
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_tiers_user_id
    ON user_tiers(user_id);

CREATE TABLE IF NOT EXISTS user_preferences (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider    VARCHAR(100) NOT NULL DEFAULT 'groq',
    model       VARCHAR(255) NOT NULL DEFAULT 'llama-3.3-70b-versatile',
    updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id
    ON user_preferences(user_id);

CREATE TABLE IF NOT EXISTS usage (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date            DATE NOT NULL DEFAULT CURRENT_DATE,
    request_count   INTEGER NOT NULL DEFAULT 0,
    token_count     INTEGER NOT NULL DEFAULT 0,
    updated_at      TIMESTAMP DEFAULT NOW(),

    -- Only one row per user per day
    UNIQUE (user_id, date)
);

CREATE INDEX IF NOT EXISTS idx_usage_user_date
    ON usage(user_id, date);