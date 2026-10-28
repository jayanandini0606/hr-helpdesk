"""
Validation & Reproducibility Verification Suite for AI-Powered HR Helpdesk.
Implements Step 8 (relational integrity, date ordering, arithmetic reconciliation)
and Step 10 (fixed-seed regeneration & checksum comparison).
"""

import hashlib
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.generate_data import generate_dataset
DB_PATH = PROJECT_ROOT / "data" / "hr_helpdesk.db"
SCHEMA_FILE = PROJECT_ROOT / "sql" / "schema.sql"


def compute_table_checksum(conn: sqlite3.Connection, table: str) -> str:
    """Computes a deterministic SHA256 checksum across all rows and columns of a table."""
    cursor = conn.execute(f"SELECT * FROM {table} ORDER BY 1")
    hasher = hashlib.sha256()
    for row in cursor.fetchall():
        row_str = "|".join("" if v is None else str(v) for v in row)
        hasher.update(row_str.encode("utf-8"))
    return hasher.hexdigest()


def validate_dataset(db_path: Path = None) -> Dict[str, Any]:
    target_db = Path(db_path) if db_path else DB_PATH
    conn = sqlite3.connect(target_db)
    conn.execute("PRAGMA foreign_keys = ON")

    report = {"errors": [], "warnings": [], "checks": {}}

    try:
        # 1. Foreign-Key Integrity
        fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        report["checks"]["foreign_key_violations"] = len(fk_violations)
        if fk_violations:
            report["errors"].append(f"Foreign key violations found: {fk_violations}")

        # 2. Arithmetic Reconciliation
        ticket_count = conn.execute("SELECT COUNT(*) FROM Ticket").fetchone()[0]
        message_count = conn.execute("SELECT COUNT(*) FROM Message").fetchone()[0]
        sla_count = conn.execute("SELECT COUNT(*) FROM SLA").fetchone()[0]
        resolution_count = conn.execute("SELECT COUNT(*) FROM Resolution").fetchone()[0]
        article_count = conn.execute("SELECT COUNT(*) FROM KnowledgeArticle").fetchone()[0]

        report["checks"]["ticket_count"] = ticket_count
        report["checks"]["message_count"] = message_count
        report["checks"]["sla_count"] = sla_count
        report["checks"]["resolution_count"] = resolution_count
        report["checks"]["article_count"] = article_count

        if ticket_count == 5000 and message_count != 20000:
            report["errors"].append(f"Expected 20,000 messages for 5,000 tickets, found {message_count}")

        # 3. Date Ordering Checks
        bad_ticket_dates = conn.execute(
            "SELECT COUNT(*) FROM Ticket WHERE updated_at < created_at"
        ).fetchone()[0]
        if bad_ticket_dates > 0:
            report["errors"].append(f"{bad_ticket_dates} tickets have updated_at < created_at")

        bad_version_dates = conn.execute(
            "SELECT COUNT(*) FROM PolicyVersion WHERE effective_to IS NOT NULL AND effective_to < effective_from"
        ).fetchone()[0]
        if bad_version_dates > 0:
            report["errors"].append(f"{bad_version_dates} policy versions have effective_to < effective_from")

        bad_sla_dates = conn.execute(
            "SELECT COUNT(*) FROM SLA WHERE resolution_due_at < response_due_at"
        ).fetchone()[0]
        if bad_sla_dates > 0:
            report["errors"].append(f"{bad_sla_dates} SLAs have resolution_due_at < response_due_at")

        # 4. Primary Key Uniqueness
        tables = [
            "Department", "Employee", "Category", "PolicyDocument", "PolicyVersion",
            "KnowledgeArticle", "Ticket", "Message", "Assignment", "SLA", "Resolution"
        ]
        for t in tables:
            pk_col = conn.execute(f"PRAGMA table_info({t})").fetchall()[0][1]
            total_rows = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            distinct_pks = conn.execute(f"SELECT COUNT(DISTINCT {pk_col}) FROM {t}").fetchone()[0]
            if total_rows != distinct_pks:
                report["errors"].append(f"Table {t} has duplicate primary keys: {total_rows} rows vs {distinct_pks} PKs")

        # 5. Allowed Enums
        bad_statuses = conn.execute("""
            SELECT COUNT(*) FROM Ticket
            WHERE status NOT IN ('Open', 'Awaiting_Employee', 'In_Progress', 'Resolved', 'Closed')
        """).fetchone()[0]
        if bad_statuses > 0:
            report["errors"].append(f"Found {bad_statuses} tickets with invalid status enum")

        bad_priorities = conn.execute("""
            SELECT COUNT(*) FROM Ticket
            WHERE priority NOT IN ('Low', 'Medium', 'High', 'Critical')
        """).fetchone()[0]
        if bad_priorities > 0:
            report["errors"].append(f"Found {bad_priorities} tickets with invalid priority enum")

        # 6. Message Sequences per ticket
        bad_seqs = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT ticket_id, COUNT(*) as cnt, MAX(sequence_number) as max_seq
                FROM Message
                GROUP BY ticket_id
                HAVING cnt <> max_seq
            )
        """).fetchone()[0]
        if bad_seqs > 0:
            report["errors"].append(f"Found {bad_seqs} tickets with non-contiguous message sequence numbers")

        report["passed"] = (len(report["errors"]) == 0)
        return report

    finally:
        conn.close()


def test_reproducibility():
    """Generates dataset twice with identical seed 20261022 and verifies 100% matching checksums."""
    print("\n" + "=" * 70)
    print("STEP 10 — FIXED-SEED REPRODUCIBILITY TEST")
    print("=" * 70)

    tables = [
        "Department", "Employee", "Category", "PolicyDocument", "PolicyVersion",
        "KnowledgeArticle", "Ticket", "Message", "Assignment", "SLA", "Resolution"
    ]

    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")

    # Run 1
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f1:
        p1 = Path(f1.name)
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f2:
        p2 = Path(f2.name)

    try:
        # Build DB 1
        c1 = sqlite3.connect(p1)
        c1.executescript(schema_sql)
        c1.close()
        generate_dataset(target_tickets=500, db_path=p1, seed=20261022, export_csv=False)

        # Build DB 2
        c2 = sqlite3.connect(p2)
        c2.executescript(schema_sql)
        c2.close()
        generate_dataset(target_tickets=500, db_path=p2, seed=20261022, export_csv=False)

        conn1 = sqlite3.connect(p1)
        conn2 = sqlite3.connect(p2)

        matches = 0
        print("\nTable Checksum Comparison (Run 1 vs Run 2):")
        for t in tables:
            hash1 = compute_table_checksum(conn1, t)
            hash2 = compute_table_checksum(conn2, t)
            status = "MATCH" if hash1 == hash2 else "MISMATCH"
            if hash1 == hash2:
                matches += 1
            print(f"  [{status}] {t:18} | Hash: {hash1[:16]}... vs {hash2[:16]}...")

        conn1.close()
        conn2.close()

        all_matched = (matches == len(tables))
        print(f"\nReproducibility Result: {matches}/{len(tables)} tables identical.")
        assert all_matched, "Reproducibility test failed! Checksums did not match."
        print(">>> 100% DETERMINISTIC REPRODUCIBILITY VERIFIED! <<<\n")
        return all_matched

    finally:
        for p in [p1, p2]:
            try:
                p.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    rep = validate_dataset()
    print("\nDATASET INTEGRITY AUDIT REPORT:")
    print("-" * 50)
    for k, v in rep["checks"].items():
        print(f"  - {k}: {v}")
    print(f"Validation Status: {'PASS' if rep['passed'] else 'FAIL'}")
    if rep["errors"]:
        print("Errors:", rep["errors"])

    test_reproducibility()
