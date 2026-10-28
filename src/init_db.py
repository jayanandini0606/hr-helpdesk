
import sqlite3
from pathlib import Path

# Project root = parent folder of src
PROJECT_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_FILE = PROJECT_ROOT / "sql" / "schema.sql"
DATABASE_FILE = PROJECT_ROOT / "data" / "hr_helpdesk.db"


def initialize_database():
    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(f"Schema not found: {SCHEMA_FILE}")

    DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_FILE)

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
        print(f"Database location: {DATABASE_FILE}")
        print(f"Number of tables: {len(rows)}")

        for row in rows:
            print(f"- {row[0]}")

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


if __name__ == "__main__":
    initialize_database()
