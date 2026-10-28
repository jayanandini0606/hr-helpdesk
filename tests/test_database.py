"""
Automated tests for database initialization, master data generation,
repeat execution idempotency, record counts, and foreign-key integrity.
"""

import sqlite3
from pathlib import Path
import pytest
from src.generate_master_data import (
    generate_master_data, DEPARTMENTS, CATEGORIES,
    EMPLOYEE_COUNT, POLICY_COUNT, ARTICLE_COUNT
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_master_data_record_counts(temp_db_path):
    """Verifies that all 6 master tables have exact expected record counts."""
    conn = sqlite3.connect(temp_db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM Department").fetchone()[0] == len(DEPARTMENTS)
        assert conn.execute("SELECT COUNT(*) FROM Category").fetchone()[0] == len(CATEGORIES)
        assert conn.execute("SELECT COUNT(*) FROM Employee").fetchone()[0] == EMPLOYEE_COUNT
        assert conn.execute("SELECT COUNT(*) FROM PolicyDocument").fetchone()[0] == POLICY_COUNT
        assert conn.execute("SELECT COUNT(*) FROM PolicyVersion").fetchone()[0] == POLICY_COUNT * 2
        assert conn.execute("SELECT COUNT(*) FROM KnowledgeArticle").fetchone()[0] == ARTICLE_COUNT
    finally:
        conn.close()


def test_foreign_key_integrity(temp_db_path):
    """Verifies zero foreign key violations across the entire database."""
    conn = sqlite3.connect(temp_db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        assert len(violations) == 0, f"Found foreign key violations: {violations}"
    finally:
        conn.close()


def test_master_data_repeat_execution_idempotency(temp_db_path):
    """Verifies that running generate_master_data repeatedly is idempotent and does not corrupt data."""
    # Run second time
    generate_master_data(db_path=temp_db_path)

    # Run third time
    generate_master_data(db_path=temp_db_path)

    conn = sqlite3.connect(temp_db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        assert len(conn.execute("PRAGMA foreign_key_check").fetchall()) == 0
        assert conn.execute("SELECT COUNT(*) FROM Employee").fetchone()[0] == EMPLOYEE_COUNT
        assert conn.execute("SELECT COUNT(*) FROM PolicyDocument").fetchone()[0] == POLICY_COUNT
        assert conn.execute("SELECT COUNT(*) FROM PolicyVersion").fetchone()[0] == POLICY_COUNT * 2
        assert conn.execute("SELECT COUNT(*) FROM KnowledgeArticle").fetchone()[0] == ARTICLE_COUNT
    finally:
        conn.close()


def test_all_twenty_policies_exist(temp_db_path):
    """Explicitly verifies that all policies POL-HR-2026-001 through POL-HR-2026-020 exist with 2 versions each."""
    conn = sqlite3.connect(temp_db_path)
    try:
        for i in range(1, 21):
            pol_id = f"POL-HR-2026-{i:03d}"
            pol = conn.execute("SELECT policy_id, title FROM PolicyDocument WHERE policy_id = ?", (pol_id,)).fetchone()
            assert pol is not None, f"Policy {pol_id} is missing from PolicyDocument!"

            ver_count = conn.execute("SELECT COUNT(*) FROM PolicyVersion WHERE policy_id = ?", (pol_id,)).fetchone()[0]
            assert ver_count == 2, f"Policy {pol_id} has {ver_count} versions (expected 2)!"
    finally:
        conn.close()


def test_knowledge_articles_cite_published_versions(temp_db_path):
    """Verifies that all published knowledge articles reference valid published policy versions."""
    conn = sqlite3.connect(temp_db_path)
    try:
        invalid_count = conn.execute("""
            SELECT COUNT(*)
            FROM KnowledgeArticle ka
            JOIN PolicyVersion pv ON ka.version_id = pv.version_id
            WHERE ka.status = 'Published' AND pv.status <> 'Published'
        """).fetchone()[0]
        assert invalid_count == 0
    finally:
        conn.close()


def test_parameterized_volume_generation_and_anomalies(tmp_path):
    """Verifies parameterized generation (e.g. 150 tickets, 600 messages) with anomaly injection."""
    from src.generate_data import generate_dataset
    db_file = tmp_path / "param_test.db"
    conn = sqlite3.connect(db_file)
    schema_sql = (PROJECT_ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    conn.close()

    res = generate_dataset(target_tickets=150, db_path=db_file, seed=20261022, export_csv=False)
    assert res["tickets"] == 150
    assert res["messages"] == 600
    assert res["anomalies"] == 4
    assert res["fk_violations"] == 0

