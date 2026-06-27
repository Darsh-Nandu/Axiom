import os
import re
from pathlib import Path
from axiom.utils.logger import logger
import psycopg2

VERSIONS_DIR = Path(__file__).parent / "versions"

def get_migration_files() -> list[tuple[int, Path]]:
    """
    Scans the versions/ directory and returns the migrations files
    """
    files = []
    pattern = re.compile(r"^V(\d+)__[\w]+\.sql$")

    for file in VERSIONS_DIR.iterdir():
        match = pattern.match(file.name)
        if match:
            version = int(match.group(1))
            files.append((version, file))

    files.sort(key=lambda x: x[0])
    return files

def ensure_migrations_table(conn) -> None:
    """
    Creates the schema migrations table if it doesn't exist yet.
    This is the table that tracks which migrations have been applied.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version     INTEGER PRIMARY KEY,
                file_name   VARCHAR(255) NOT NULL,
                applied_at  TIMESTAMP DEFAULT NOW()
            );
            """
        )
    conn.commit()

def get_applied_versions(conn) -> set[int]:
    """
    Returns a set of versions that have already been applied.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations;")
        rows=cur.fetchall()
    return {row[0] for row in rows}

def apply_migration(conn, version: int, filepath: Path) -> None:
    """
    Reads and applies a single migration file.
    Records it in schema_migrations on success.
    Rolls back on failure.
    """
    sql = filepath.read_text()

    try:
        with conn.cursor as cur:
            cur.execute(sql)
            cur.execute(
                """
                INSERT INTO schema_migrations (versions, filepath) VALUES (%s, %s);
                """,
                (version, filepath)
            )
        conn.commit()
        logger.info(f"Migrations applied: {filepath.name}")

    except Exception as e:
        conn.rollback()
        logger.error(f"Migrations failed: {filepath.name} - {e}")
        raise

def run_migrations(conn) -> None:
    """
    Main entry point. Called on app startup.
    Applies all pending migrations in version order.
    """
    ensure_migrations_table(conn)
    applied = get_applied_versions(conn)
    migration_files = get_migration_files()
 
    pending = [(v, f) for v, f in migration_files if v not in applied]
 
    if not pending:
        logger.info("Database is up to date. No migrations to apply.")
        return
 
    logger.info(f"Found {len(pending)} pending migration(s). Applying...")
 
    for version, filepath in pending:
        apply_migration(conn, version, filepath)
 
    logger.info("All migrations applied successfully.")