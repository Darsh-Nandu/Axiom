-- V001: Initial schema
-- Creates users, sessions, and messages tables.
-- messages table supports: human, ai, tool_call, tool_result, agent_call, agent_result roles.

CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(255) UNIQUE NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
)

CREATE TABLE IF NOT EXISTS sessions (
    id          UUID PRIMARY KEY DEFAULT get_random_uuid(),
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMP DEFAULT NOW()
)

CREATE TABLE IF NOT EXISTS messages(
    id              SERIAL PRIMARY KEY,
    session_id      UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role            VARCHAR(50) NOT NULL CHECK (role IN (
                        'human',
                        'ai',
                        'tool_call',
                        'tool_result',
                        'agent_call',
                        'agent_result'
                    )),
    content         TEXT NOT NULL,
    tool_name       VARCHAR(255),
    tool_call_id    VARCHAR(255),
    agent_name      VARCHAR(255),
    created_at      TIMESTAMP DEFAULT NOW()
)

CREATE INDEX IF NOT EXISTS idx_messages_session_id
    ON messages(session_id);

CREATE INDEX IF NOT EXISTS idx_messages_created_at
    ON messages(session_id, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id
    ON sessions(user_id);
 