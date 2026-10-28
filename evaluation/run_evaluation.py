"""
Evaluation runner for AI-Powered HR Helpdesk.
Executes synthetic evaluation test cases against the live classification,
retrieval, and ticket lifecycle engines. Produces structured audit report
and saves evaluation_results.json.
"""

import json
import sqlite3
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.generate_master_data import generate_master_data
from src.ticket_service import create_ticket, get_ticket

SCHEMA_FILE = PROJECT_ROOT / "sql" / "schema.sql"
TEST_CASES_FILE = PROJECT_ROOT / "evaluation" / "test_cases.json"
RESULTS_FILE = PROJECT_ROOT / "evaluation" / "evaluation_results.json"


def setup_eval_database(db_file: Path) -> Path:
    if db_file.exists():
        try:
            db_file.unlink()
        except Exception:
            pass

    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys = ON")
    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    conn.close()
    generate_master_data(db_path=db_file)
    return db_file


def run_evaluation():
    if not TEST_CASES_FILE.exists():
        raise FileNotFoundError(f"Test cases file not found: {TEST_CASES_FILE}")

    with open(TEST_CASES_FILE, "r", encoding="utf-8") as f:
        cases = json.load(f)

    # Use a unique temporary db path
    eval_db = Path(tempfile.gettempdir()) / f"eval_hr_{uuid.uuid4().hex[:8]}.db"

    try:
        setup_eval_database(eval_db)

        results = []
        passed_count = 0
        failed_count = 0

        print(f"\n{'='*75}")
        print(f"RUNNING AI HR HELPDESK EVALUATION SUITE ({len(cases)} TEST CASES)")
        print(f"{'='*75}\n")

        for c in cases:
            case_id = c["id"]
            name = c["name"]
            subject = c["subject"]
            desc = c["description"]
            exp_cat = c["expected_category"]
            exp_queue = c["expected_queue"]
            exp_outcome = c["expected_outcome"]
            exp_policy = c.get("expected_policy_id")

            # Create ticket
            ticket = create_ticket(
                employee_id="EMP-000006",
                subject=subject,
                description=desc,
                created_at="2026-10-28T09:00:00Z",
                db_path=eval_db
            )

            bundle = get_ticket(ticket["ticket_id"], db_path=eval_db)

            actual_cat = ticket["category_id"]
            actual_queue = ticket["assigned_queue"]
            actual_outcome = ticket["outcome"]
            actual_sensitive = ticket["sensitive_flag"]
            actual_citations = [cit["policy_id"] for cit in bundle["citations"]]

            # Verification assertions
            cat_match = (actual_cat == exp_cat)
            queue_match = (actual_queue == exp_queue)
            outcome_match = (actual_outcome == exp_outcome)

            policy_match = True
            if exp_policy and exp_outcome == "Answered":
                policy_match = (exp_policy in actual_citations)

            # Sensitive guardrail check: if sensitive, outcome must NOT be Answered
            guardrail_check = True
            if actual_sensitive == 1 and actual_outcome == "Answered":
                guardrail_check = False

            passed = cat_match and queue_match and outcome_match and policy_match and guardrail_check

            if passed:
                passed_count += 1
                status_str = "PASS"
            else:
                failed_count += 1
                status_str = "FAIL"

            print(f"[{status_str}] {case_id}: {name}")
            print(f"       Category: {actual_cat} (Exp: {exp_cat}) | Queue: {actual_queue} (Exp: {exp_queue}) | Outcome: {actual_outcome}")
            if not passed:
                print(f"       >>> Failure Details: cat_ok={cat_match}, queue_ok={queue_match}, outcome_ok={outcome_match}, policy_ok={policy_match}, guardrail={guardrail_check}")

            results.append({
                "test_case_id": case_id,
                "name": name,
                "subject": subject,
                "expected_category": exp_cat,
                "actual_category": actual_cat,
                "expected_queue": exp_queue,
                "actual_queue": actual_queue,
                "expected_outcome": exp_outcome,
                "actual_outcome": actual_outcome,
                "sensitive_flag": actual_sensitive,
                "citations": actual_citations,
                "passed": passed
            })

        pass_rate = round((passed_count / len(cases) * 100), 1)

        summary = {
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "total_test_cases": len(cases),
            "passed": passed_count,
            "failed": failed_count,
            "pass_rate_percentage": pass_rate,
            "results": results
        }

        with open(RESULTS_FILE, "w", encoding="utf-8") as out_f:
            json.dump(summary, out_f, indent=2)

        print(f"\n{'-'*75}")
        print(f"EVALUATION SUMMARY: {passed_count}/{len(cases)} PASSED ({pass_rate}%)")
        print(f"Results written to: {RESULTS_FILE}")
        print(f"{'-'*75}\n")

        return summary

    finally:
        # Cleanup temp db
        try:
            if eval_db.exists():
                eval_db.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    run_evaluation()
