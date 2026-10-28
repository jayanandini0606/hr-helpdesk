"""
Database utility module for AI-Powered HR Helpdesk.
Provides connection pooling, row factory, parameterized helper methods,
and transaction management with enforced foreign keys.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "hr_helpdesk.db"


def get_db_path() -> Path:
    env_path = os.getenv("DATABASE_PATH")
    if env_path:
        return Path(env_path) if Path(env_path).is_absolute() else PROJECT_ROOT / env_path
    return DEFAULT_DB_PATH


def get_connection(db_path: Path = None) -> sqlite3.Connection:
    target_path = Path(db_path) if db_path else get_db_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_session(db_path: Path = None):
    """Context manager for transactional database operations."""
    conn = get_connection(db_path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def query_all(sql: str, params: tuple = (), db_path: Path = None) -> list:
    """Execute a SELECT query and return all rows as list of dicts."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def query_one(sql: str, params: tuple = (), db_path: Path = None) -> dict | None:
    """Execute a SELECT query and return a single row as dict, or None."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None


def execute_write(sql: str, params: tuple = (), db_path: Path = None) -> int:
    """Execute an INSERT/UPDATE/DELETE query within a transaction."""
    with db_session(db_path) as conn:
        cursor = conn.execute(sql, params)
        return cursor.rowcount
