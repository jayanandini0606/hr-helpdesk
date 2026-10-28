"""
Automated tests for ticket classification, priority assignment,
and sensitive-case detection and routing.
"""

import pytest
from src.classifier import classify_request


def test_classify_all_five_categories():
    """Verifies that routine requests in each of the 5 categories are correctly classified."""
    cases = [
        ("Health insurance dental enrollment", "I want to add dental coverage to my existing health plan.", "CAT-001"),
        ("Annual leave balance request", "How many days of paid vacation do I have remaining this calendar year?", "CAT-002"),
        ("Accessing monthly payslip PDF", "Where can I download my salary slip for the month?", "CAT-003"),
        ("New hire laptop and monitor delivery", "When will my equipment and credentials arrive for orientation?", "CAT-004"),
        ("General workplace ethics code", "Where can I read the general code of conduct?", "CAT-005"),
    ]
    for subject, desc, expected_cat in cases:
        result = classify_request(subject, desc)
        assert result["category_id"] == expected_cat, f"Failed for '{subject}': got {result['category_id']}, expected {expected_cat}"
        assert result["sensitive_flag"] == 0
        assert result["auto_resolvable"] is True


def test_sensitive_harassment_detection():
    """Harassment complaints must be flagged sensitive, Critical priority, routed to HR-Confidential."""
    result = classify_request(
        subject="Report of sexual harassment by senior colleague",
        description="I am being subjected to repeated verbal harassment and unwanted advances by my team lead."
    )
    assert result["sensitive_flag"] == 1
    assert result["priority"] == "Critical"
    assert result["assigned_queue"] == "HR-Confidential"
    assert result["auto_resolvable"] is False
    assert "Harassment / Discrimination" in result["sensitive_types"]


def test_sensitive_discrimination_detection():
    """Discrimination / hostile environment reports must be flagged sensitive."""
    result = classify_request(
        subject="Hostile work environment and racial discrimination",
        description="I am facing unfair treatment and bias from management during performance evaluations."
    )
    assert result["sensitive_flag"] == 1
    assert result["priority"] in ("Critical", "High")
    assert result["assigned_queue"] == "HR-Confidential"
    assert result["auto_resolvable"] is False


def test_sensitive_grievance_detection():
    """Formal employee grievances must be routed to HR-Confidential."""
    result = classify_request(
        subject="Filing a formal grievance against supervisor",
        description="I wish to submit an official grievance detailing managerial misconduct and retaliatory actions."
    )
    assert result["sensitive_flag"] == 1
    assert result["assigned_queue"] == "HR-Confidential"
    assert result["auto_resolvable"] is False


def test_sensitive_payroll_dispute_detection():
    """Unexpected salary deductions or missing pay must route to Payroll queue as High priority sensitive case."""
    result = classify_request(
        subject="Unexpected salary deduction on October paycheck",
        description="There is an unexpected deduction of $500 from my monthly salary without explanation. Please audit."
    )
    assert result["sensitive_flag"] == 1
    assert result["category_id"] == "CAT-003"
    assert result["assigned_queue"] == "Payroll"
    assert result["priority"] == "High"
    assert result["auto_resolvable"] is False


def test_sensitive_third_party_private_info_detection():
    """Requests asking about another employee's private compensation or records must be flagged."""
    result = classify_request(
        subject="Inquiry regarding coworker's salary band",
        description="Can you tell me what my colleague's salary and bonus numbers are for comparison?"
    )
    assert result["sensitive_flag"] == 1
    assert result["assigned_queue"] == "HR-Confidential"
    assert result["auto_resolvable"] is False


def test_priority_escalation_for_urgent_routine_request():
    """Routine requests marked urgent escalate priority."""
    result = classify_request(
        subject="Urgent: Annual leave request needed immediately for medical appointment",
        description="I need emergency leave approved today for an urgent doctor appointment."
    )
    assert result["priority"] == "High"
    assert result["sensitive_flag"] == 0
