"""
Automated tests for policy retrieval, effective date and status version resolution,
citation grounding, and ungrounded fallbacks.
"""

import pytest
from src.policy_retrieval import (
    retrieve_relevant_knowledge,
    find_applicable_policy_version,
    get_all_policies_summary
)
from src.response_service import generate_grounded_answer


def test_retrieval_payslip_access(temp_db_path):
    """Retrieves Payslip Access policy and articles accurately."""
    results = retrieve_relevant_knowledge(
        query_text="Where can I download my monthly payslip PDF?",
        category_id="CAT-003",
        as_of_date="2026-10-28",
        db_path=temp_db_path
    )
    assert len(results) > 0
    top = results[0]
    assert top["policy_id"] == "POL-HR-2026-010"
    assert "Payslip" in top["policy_title"]
    assert top["version_number"] == 2
    assert top["version_status"] == "Published"


def test_retrieval_sick_leave_policy(temp_db_path):
    """Retrieves Sick Leave policy accurately."""
    results = retrieve_relevant_knowledge(
        query_text="How many sick leave days are allowed per year?",
        category_id="CAT-002",
        as_of_date="2026-10-28",
        db_path=temp_db_path
    )
    assert len(results) > 0
    top = results[0]
    assert top["policy_id"] == "POL-HR-2026-006"
    assert "Sick Leave" in top["policy_title"]


def test_effective_date_version_selection_does_not_just_take_max_number(temp_db_path):
    """
    POL-HR-2026-019 has Version 1 (Published) and Version 2 (Draft, effective 2027).
    Querying as of 2026-10-28 MUST select Version 1, NOT Version 2!
    """
    version = find_applicable_policy_version(
        policy_id="POL-HR-2026-019",
        as_of_date="2026-10-28",
        db_path=temp_db_path
    )
    assert version is not None
    assert version["version_number"] == 1, (
        f"Expected version 1 (Published), but got version {version['version_number']}. "
        "System must not blindly pick MAX(version_number) when Version 2 is Draft!"
    )
    assert version["status"] == "Published"


def test_effective_date_retired_version_not_selected_for_current_date(temp_db_path):
    """
    POL-HR-2026-001 has Version 1 (Retired, ended 2026-03-31) and Version 2 (Published from 2026-04-01).
    Querying as of 2026-10-28 MUST select Version 2.
    """
    version = find_applicable_policy_version(
        policy_id="POL-HR-2026-001",
        as_of_date="2026-10-28",
        db_path=temp_db_path
    )
    assert version is not None
    assert version["version_number"] == 2
    assert version["status"] == "Published"


def test_grounded_answer_includes_citations(temp_db_path):
    """Verifies that generated grounded answer contains exact citations."""
    articles = retrieve_relevant_knowledge(
        query_text="payslip access portal instructions",
        category_id="CAT-003",
        as_of_date="2026-10-28",
        db_path=temp_db_path
    )
    ans = generate_grounded_answer(
        ticket_id="TKT-TEST-001",
        subject="How do I get my payslip?",
        description="I need payslip guidance.",
        retrieved_articles=articles
    )
    assert ans["outcome"] == "Answered"
    assert ans["message_type"] == "Answer"
    assert len(ans["citations"]) > 0
    assert "POL-HR-2026-010" in ans["message_text"]
    assert "Version" in ans["message_text"]


def test_fallback_when_no_policy_found():
    """When no relevant articles are retrieved, system states evidence is unavailable without hallucinating."""
    ans = generate_grounded_answer(
        ticket_id="TKT-TEST-002",
        subject="Request for paid international sabbatical",
        description="Can I take 6 months off with full pay?",
        retrieved_articles=[]
    )
    assert ans["outcome"] == "Unresolved"
    assert ans["message_type"] == "Clarification"
    assert len(ans["citations"]) == 0
    assert "could not locate an authoritative policy" in ans["message_text"].lower()
