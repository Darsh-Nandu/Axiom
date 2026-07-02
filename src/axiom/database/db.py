"""
Database layer for Axiom.

This file is the ONLY place that talks to PostgreSQL directly.
Nothing else in the codebase should import psycopg2 or write SQL.

Responsibilities:
- Managing the connection pool
- All CRUD operations for:
    users, sessions, messages,
    user_tiers, user_preferences, usage
- Running migrations on startup

Environment variables required in .env:
    DB_HOST      e.g. localhost
    DB_PORT      e.g. 5432
    DB_NAME      e.g. axiom
    DB_USER      e.g. postgres
    DB_PASSWORD  e.g. yourpassword
"""

import os
import sys
from pathlib import Path
from typing import Optional
from datetime import date
from dotenv import load_dotenv
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from axiom.utils.logger import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from migrations.migrate import run_migrations

load_dotenv()


# CONNECTION POOL

_pool: Optional[pool.SimpleConnectionPool] = None


def init_db() -> None:
    """
    Call once on app startup.
    Creates the connection pool and runs pending migrations.
    """
    global _pool
    try:
        _pool = pool.SimpleConnectionPool(
            minconn=2,
            maxconn=10,
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            dbname=os.getenv("DB_NAME", "axiom"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )
        logger.info("Database connection pool created.")

        conn = _pool.getconn()
        try:
            run_migrations(conn)
        finally:
            _pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to initialise database: {e}")
        raise


def get_conn():
    """Borrow a connection from the pool."""
    if _pool is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _pool.getconn()


def put_conn(conn) -> None:
    """Return a connection back to the pool."""
    if _pool:
        _pool.putconn(conn)


def close_db() -> None:
    """Call on app shutdown to close all connections cleanly."""
    if _pool:
        _pool.closeall()
        logger.info("Database connection pool closed.")


# USERS

def create_user(username: str, email: str, password_hash: str) -> dict:
    """
    Creates a new user with hashed password.
    Also creates default tier and preferences rows for the user.
    Raises if username or email already exists.
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # Create the user
            cur.execute(
                """
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, username, email, created_at;
                """,
                (username, email, password_hash)
            )
            user = dict(cur.fetchone())
            user_id = user["id"]

            # Auto-create default tier (free)
            cur.execute(
                "INSERT INTO user_tiers (user_id) VALUES (%s);",
                (user_id,)
            )

            # Auto-create default preferences
            cur.execute(
                "INSERT INTO user_preferences (user_id) VALUES (%s);",
                (user_id,)
            )

        conn.commit()
        logger.info(f"User created: {username} ({email})")
        return user

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create user '{username}': {e}")
        raise

    finally:
        put_conn(conn)


def get_user_by_username(username: str) -> Optional[dict]:
    """Fetches a user by username. Returns None if not found."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, username, email, password_hash, created_at
                FROM users WHERE username = %s;
                """,
                (username,)
            )
            row = cur.fetchone()
        return dict(row) if row else None

    except Exception as e:
        logger.error(f"Failed to get user '{username}': {e}")
        raise

    finally:
        put_conn(conn)


def get_user_by_email(email: str) -> Optional[dict]:
    """Fetches a user by email. Returns None if not found."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, username, email, password_hash, created_at
                FROM users WHERE email = %s;
                """,
                (email,)
            )
            row = cur.fetchone()
        return dict(row) if row else None

    except Exception as e:
        logger.error(f"Failed to get user by email '{email}': {e}")
        raise

    finally:
        put_conn(conn)


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Fetches a user by ID. Used when verifying JWT tokens."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, username, email, created_at
                FROM users WHERE id = %s;
                """,
                (user_id,)
            )
            row = cur.fetchone()
        return dict(row) if row else None

    except Exception as e:
        logger.error(f"Failed to get user by id '{user_id}': {e}")
        raise

    finally:
        put_conn(conn)


# SESSIONS

def create_session(user_id: int) -> dict:
    """Starts a new conversation session for a user."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO sessions (user_id)
                VALUES (%s)
                RETURNING id, user_id, created_at;
                """,
                (user_id,)
            )
            session = dict(cur.fetchone())
        conn.commit()
        logger.info(f"Session created for user_id={user_id}: {session['id']}")
        return session

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create session for user_id={user_id}: {e}")
        raise

    finally:
        put_conn(conn)


def get_sessions(user_id: int) -> list[dict]:
    """Returns all sessions for a user, newest first."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, user_id, created_at
                FROM sessions
                WHERE user_id = %s
                ORDER BY created_at DESC;
                """,
                (user_id,)
            )
            return [dict(row) for row in cur.fetchall()]

    except Exception as e:
        logger.error(f"Failed to get sessions for user_id={user_id}: {e}")
        raise

    finally:
        put_conn(conn)


def delete_session(session_id: str) -> None:
    """Deletes a session and all its messages (CASCADE handles messages)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE id = %s;", (session_id,))
        conn.commit()
        logger.info(f"Session deleted: {session_id}")

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to delete session {session_id}: {e}")
        raise

    finally:
        put_conn(conn)


# MESSAGES

def save_message(
    session_id: str,
    role: str,
    content: str,
    tool_name: Optional[str] = None,
    tool_call_id: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> dict:
    """
    Saves any type of message to the messages table.
    role must be one of:
        human, ai, tool_call, tool_result, agent_call, agent_result
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO messages
                    (session_id, role, content, tool_name, tool_call_id, agent_name)
                VALUES
                    (%s, %s, %s, %s, %s, %s)
                RETURNING id, session_id, role, content,
                          tool_name, tool_call_id, agent_name, created_at;
                """,
                (session_id, role, content, tool_name, tool_call_id, agent_name)
            )
            message = dict(cur.fetchone())
        conn.commit()
        return message

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to save message (role={role}) for session {session_id}: {e}")
        raise

    finally:
        put_conn(conn)


def get_messages(session_id: str) -> list[dict]:
    """Fetches all messages for a session in chronological order."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, session_id, role, content,
                       tool_name, tool_call_id, agent_name, created_at
                FROM messages
                WHERE session_id = %s
                ORDER BY created_at ASC;
                """,
                (session_id,)
            )
            return [dict(row) for row in cur.fetchall()]

    except Exception as e:
        logger.error(f"Failed to get messages for session {session_id}: {e}")
        raise

    finally:
        put_conn(conn)


# USER TIERS

def get_user_tier(user_id: int) -> Optional[dict]:
    """
    Returns the tier info for a user.
    Used by auth layer to check which models they can access
    and what their rate limits are.
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT user_id, tier, allowed_models,
                       max_requests_per_day, max_tokens_per_day, updated_at
                FROM user_tiers WHERE user_id = %s;
                """,
                (user_id,)
            )
            row = cur.fetchone()
        return dict(row) if row else None

    except Exception as e:
        logger.error(f"Failed to get tier for user_id={user_id}: {e}")
        raise

    finally:
        put_conn(conn)


def update_user_tier(
    user_id: int,
    tier: str,
    allowed_models: list[str],
    max_requests_per_day: int,
    max_tokens_per_day: int,
) -> dict:
    """
    Updates a user's tier and limits.
    Called when upgrading a user from free → pro → admin.
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE user_tiers
                SET tier = %s,
                    allowed_models = %s,
                    max_requests_per_day = %s,
                    max_tokens_per_day = %s,
                    updated_at = NOW()
                WHERE user_id = %s
                RETURNING *;
                """,
                (tier, allowed_models, max_requests_per_day, max_tokens_per_day, user_id)
            )
            row = cur.fetchone()
        conn.commit()
        logger.info(f"Tier updated for user_id={user_id}: {tier}")
        return dict(row)

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to update tier for user_id={user_id}: {e}")
        raise

    finally:
        put_conn(conn)


# USER PREFERENCES

def get_user_preferences(user_id: int) -> Optional[dict]:
    """Returns the model and provider the user has chosen."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT user_id, provider, model, updated_at
                FROM user_preferences WHERE user_id = %s;
                """,
                (user_id,)
            )
            row = cur.fetchone()
        return dict(row) if row else None

    except Exception as e:
        logger.error(f"Failed to get preferences for user_id={user_id}: {e}")
        raise

    finally:
        put_conn(conn)


def update_user_preferences(user_id: int, provider: str, model: str) -> dict:
    """
    Saves the user's model choice.
    Uses upsert — inserts if not exists, updates if exists.
    Called whenever the user switches model in the UI.
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO user_preferences (user_id, provider, model, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE
                    SET provider   = EXCLUDED.provider,
                        model      = EXCLUDED.model,
                        updated_at = NOW()
                RETURNING user_id, provider, model, updated_at;
                """,
                (user_id, provider, model)
            )
            row = cur.fetchone()
        conn.commit()
        logger.info(f"Preferences updated for user_id={user_id}: {provider}/{model}")
        return dict(row)

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to update preferences for user_id={user_id}: {e}")
        raise

    finally:
        put_conn(conn)


# USAGE

def get_usage_today(user_id: int) -> dict:
    """
    Returns today's usage for a user.
    If no usage row exists yet today, returns zeros.
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT user_id, date, request_count, token_count, updated_at
                FROM usage
                WHERE user_id = %s AND date = CURRENT_DATE;
                """,
                (user_id,)
            )
            row = cur.fetchone()

        # No usage yet today — return zeros
        if not row:
            return {
                "user_id": user_id,
                "date": date.today().isoformat(),
                "request_count": 0,
                "token_count": 0,
            }

        return dict(row)

    except Exception as e:
        logger.error(f"Failed to get usage for user_id={user_id}: {e}")
        raise

    finally:
        put_conn(conn)


def increment_usage(user_id: int, tokens_used: int) -> dict:
    """
    Increments request count by 1 and adds tokens_used to token count.
    Uses upsert — creates today's row if it doesn't exist yet.
    Call this after every successful LLM response.
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO usage (user_id, date, request_count, token_count)
                VALUES (%s, CURRENT_DATE, 1, %s)
                ON CONFLICT (user_id, date) DO UPDATE
                    SET request_count = usage.request_count + 1,
                        token_count   = usage.token_count + EXCLUDED.token_count,
                        updated_at    = NOW()
                RETURNING user_id, date, request_count, token_count;
                """,
                (user_id, tokens_used)
            )
            row = cur.fetchone()
        conn.commit()
        logger.info(
            f"Usage updated for user_id={user_id}: "
            f"{row['request_count']} requests, {row['token_count']} tokens today."
        )
        return dict(row)

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to increment usage for user_id={user_id}: {e}")
        raise

    finally:
        put_conn(conn)