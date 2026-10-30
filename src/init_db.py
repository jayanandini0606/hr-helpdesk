import sqlite3
from pathlib import Path
from typing import Optional

# Project root = parent folder of src
PROJECT_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_FILE = PROJECT_ROOT / "sql" / "schema.sql"
DATABASE_FILE = PROJECT_ROOT / "data" / "hr_helpdesk.db"


def initialize_database(db_path: Optional[Path] = None):
    """Initializes SQLite schema from sql/schema.sql."""
    target_db = Path(db_path) if db_path else DATABASE_FILE
    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(f"Schema not found: {SCHEMA_FILE}")

    target_db.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(target_db))

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        schema = SCHEMA_FILE.read_text(encoding="utf-8")
        connection.executescript(schema)

        # Confirm that SQLite has created the tables.
        rows = connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

        print("Database initialized successfully!")
        print(f"Database location: {target_db}")
        print(f"Number of tables: {len(rows)}")

        # Check foreign-key definitions for existing records.
        violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if violations:
            print("Foreign-key violations:", violations)
        else:
            print("Foreign-key check passed!")

    finally:
        connection.close()


# Alias for backward compatibility
init_database = initialize_database


if __name__ == "__main__":
    initialize_database()
