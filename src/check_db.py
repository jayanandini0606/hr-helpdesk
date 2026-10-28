"""
Database verification utility for the AI-Powered HR Helpdesk.
Checks table presence, foreign keys, database integrity, and record counts.
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "hr_helpdesk.db"


def verify_database(db_path=None):
    target = Path(db_path) if db_path else DB_PATH
    if not target.exists():
        print(f"Database not found at {target}")
        return False

    connection = sqlite3.connect(target)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        tables = connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

        fk_enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        fk_violations = connection.execute("PRAGMA foreign_key_check").fetchall()

        print("=== DATABASE HEALTH CHECK ===")
        print(f"Path: {target}")
        print(f"Tables ({len(tables)}): {[t[0] for t in tables]}")
        print(f"Foreign keys enabled: {fk_enabled}")
        print(f"Integrity check: {integrity}")
        print(f"Foreign key violations: {fk_violations}")

        counts = {}
        for t in tables:
            t_name = t[0]
            cnt = connection.execute(f"SELECT COUNT(*) FROM {t_name}").fetchone()[0]
            counts[t_name] = cnt
            print(f"  - {t_name}: {cnt} records")

        return fk_enabled and integrity == "ok" and len(fk_violations) == 0
    finally:
        connection.close()


if __name__ == "__main__":
    verify_database()
