"""
Automated tests for ticket lifecycle, message persistence, status transitions,
assignment history, sensitive case guardrails, and event auditing.
"""

import pytest
from src.ticket_service import (
    create_ticket, get_ticket, add_ticket_message,
    reassign_ticket, update_ticket_status, list_tickets
)


def test_create_routine_ticket_success(temp_db_path):
    """Routine ticket is created, answered with policy citations, and resolved."""
    result = create_ticket(
        employee_id="EMP-000006",
        subject="How do I access my monthly payslip?",
        description="I am looking for guidance on where to view and download my monthly salary payslips.",
        db_path=temp_db_path
    )
    assert result["ticket_id"].startswith("TKT-2026-")
    assert result["status"] == "Resolved"
    assert result["sensitive_flag"] == 0
    assert result["outcome"] == "Answered"
    assert len(result["citations"]) > 0

    # Retrieve full ticket bundle
    bundle = get_ticket(result["ticket_id"], db_path=temp_db_path)
    assert bundle is not None
    assert len(bundle["messages"]) == 2
    assert bundle["messages"][0]["sender_type"] == "Employee"
    assert bundle["messages"][1]["sender_type"] == "Assistant"
    assert bundle["messages"][1]["message_type"] == "Answer"
    assert len(bundle["citations"]) > 0
    assert bundle["resolution"]["outcome"] == "Answered"
    assert len(bundle["events"]) >= 2  # Created + Resolved


def test_sensitive_ticket_never_auto_resolved(temp_db_path):
    """Sensitive ticket must NEVER be auto-resolved; it must escalate and remain In_Progress."""
    result = create_ticket(
        employee_id="EMP-000007",
        subject="Harassment report regarding department director",
        description="I am being harassed and subjected to retaliatory threats in my department.",
        db_path=temp_db_path
    )
    assert result["sensitive_flag"] == 1
    assert result["status"] == "In_Progress"
    assert result["assigned_queue"] == "HR-Confidential"
    assert result["outcome"] == "Escalated"

    bundle = get_ticket(result["ticket_id"], db_path=temp_db_path)
    assert bundle["ticket"]["status"] == "In_Progress"
    assert bundle["ticket"]["status"] != "Resolved"
    assert bundle["resolution"]["outcome"] == "Escalated"
    assert bundle["messages"][1]["message_type"] == "Escalation"


def test_create_ticket_invalid_employee_raises_error(temp_db_path):
    """Creating a ticket for a non-existent employee must raise ValueError."""
    with pytest.raises(ValueError, match="does not exist"):
        create_ticket(
            employee_id="EMP-999999",
            subject="Test subject",
            description="Test description",
            db_path=temp_db_path
        )


def test_ticket_reassignment_preserves_history(temp_db_path):
    """Reassignment closes previous assignment and creates a new one preserving history."""
    t = create_ticket(
        employee_id="EMP-000008",
        subject="Leave calendar query",
        description="When are public holidays observed?",
        db_path=temp_db_path
    )
    tid = t["ticket_id"]

    # Reassign
    reassign_ticket(
        ticket_id=tid,
        new_queue="HR-General",
        new_assignee="EMP-000001",
        reason="Transferred to HR generalist for location-specific calendar",
        db_path=temp_db_path
    )

    bundle = get_ticket(tid, db_path=temp_db_path)
    assert len(bundle["assignments"]) == 2
    assert bundle["assignments"][0]["ended_at"] is not None
    assert bundle["assignments"][1]["ended_at"] is None
    assert bundle["assignments"][1]["assigned_queue"] == "HR-General"


def test_ticket_status_transition_and_event_trail(temp_db_path):
    """Status updates record audit events and validate allowed statuses."""
    t = create_ticket(
        employee_id="EMP-000009",
        subject="Benefits question",
        description="How to add dependent child?",
        db_path=temp_db_path
    )
    tid = t["ticket_id"]

    # Update to Closed
    success = update_ticket_status(
        ticket_id=tid,
        new_status="Closed",
        reason="Employee confirmed resolution via self-service",
        resolution_outcome="Answered",
        db_path=temp_db_path
    )
    assert success is True

    bundle = get_ticket(tid, db_path=temp_db_path)
    assert bundle["ticket"]["status"] == "Closed"
    assert any(e["new_status"] == "Closed" for e in bundle["events"])

    # Attempt invalid status
    with pytest.raises(ValueError, match="Invalid status"):
        update_ticket_status(
            ticket_id=tid,
            new_status="Archived_Invalid",
            reason="Illegal status test",
            db_path=temp_db_path
        )


def test_add_message_increments_sequence(temp_db_path):
    """Adding a follow-up message increments sequence_number correctly."""
    t = create_ticket(
        employee_id="EMP-000010",
        subject="Orientation schedule",
        description="When is orientation?",
        db_path=temp_db_path
    )
    tid = t["ticket_id"]

    msg = add_ticket_message(
        ticket_id=tid,
        sender_type="Employee",
        message_text="Thank you, is it online or in person?",
        message_type="Clarification",
        db_path=temp_db_path
    )
    assert msg["sequence_number"] == 3

    bundle = get_ticket(tid, db_path=temp_db_path)
    assert len(bundle["messages"]) == 3
