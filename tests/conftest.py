"""
Pytest configuration and shared fixtures for AI-Powered HR Helpdesk tests.
Uses temporary isolated databases so tests never corrupt production/demo data.
"""

import os
import sys
import sqlite3
import tempfile
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.generate_master_data import generate_master_data
SCHEMA_FILE = PROJECT_ROOT / "sql" / "schema.sql"


@pytest.fixture
def temp_db_path(tmp_path):
    """Creates a temporary, isolated SQLite database initialized with schema and master data."""
    db_file = tmp_path / "test_hr_helpdesk.db"

    # Initialize schema
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys = ON")
    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    conn.close()

    # Seed master data
    generate_master_data(db_path=db_file)

    return db_file
