
import sqlite3
from pathlib import Path

db_path = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "hr_helpdesk.db"
)

connection = sqlite3.connect(db_path)
connection.execute("PRAGMA foreign_keys = ON")

for table in ["Department", "Category", "PolicyDocument", "PolicyVersion"]:
    print(f"\n--- {table} schema ---")

    schema = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    ).fetchone()

    print(schema[0] if schema else "TABLE NOT FOUND")

    print(f"\nForeign keys for {table}:")
    for fk in connection.execute(
        f'PRAGMA foreign_key_list("{table}")'
    ):
        print(fk)

print("\n--- Existing database foreign-key violations ---")
print(connection.execute("PRAGMA foreign_key_check").fetchall())

connection.close()
