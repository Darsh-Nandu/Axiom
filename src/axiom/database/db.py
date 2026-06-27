import os
import uuid
from typing import Optional
from dotenv import load_dotenv
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from axiom.utils.logger import logger
from axiom.migrations.migrate import run_migrations

load_dotenv()

_pool: Optional[pool.SimpleConnectionPool] = None

def init_db() -> None:
    """
    Call once on startup.
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
    """Borrows a connection from the pool."""
    if _pool is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _pool.getconn()

def put_conn(conn) -> None:
    """Returns a connection back too pool."""
    if _pool:
        _pool.putconn(conn)

def close_db() -> None:
    """Call on app shutdown to close all connections cleanly."""
    if _pool:
        _pool.closeall()
        logger.info("Database connection pool closed.")


# Users

def create_user(username: str) -> dict:
    """
    Creates a new user.
    Raises an error if username already exists.
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO users (username),
                VALUES (%s),
                RETURNING id, username, created_at;
                """
                (username,)
            )
            user = dict(cur.fetchone)
        conn.commit()
        logger.info(f"User created: {username}")
        return user

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create user '{username}': {e}")
        raise

    finally:
        put_conn(conn)


def get_user(username: str) -> Optional[dict]:
    """
    Fetches a user by username.
    Returns None if user doesn't exist.
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, username, created_at FROM users WHERE username = %s;",
                (username,)
            )
            row = cur.fetchone()
        return dict(row) if row else None
 
    except Exception as e:
        logger.error(f"Failed to get user '{username}': {e}")
        raise
 
    finally:
        put_conn(conn)


# Sessions

def create_session(user_id: int) -> dict:
    """
    Starts a new conversation session for a user.
    Returns the created session row (with UUID id).
    """
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
    """
    Returns all sessions for a user, newest first.
    Useful for showing a sidebar of past conversations.
    """
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
    """
    Deletes a session and all its messages (CASCADE handles messages).
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM sessions WHERE id = %s;",
                (session_id,)
            )
        conn.commit()
        logger.info(f"Session deleted: {session_id}")
 
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to delete session {session_id}: {e}")
        raise
 
    finally:
        put_conn(conn)


# Messages
                
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
    This is the single function all message types go through.
 
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
    """
    Fetches all messages for a session in chronological order.
    This is what memory.py calls to rebuild conversation history.
    """
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