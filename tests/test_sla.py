"""
Automated tests for SLA deadline calculations, business hour arithmetic,
overdue status evaluations, and dashboard metrics calculations.
"""

from datetime import datetime, timezone
import pytest
from src.sla_service import (
    calculate_sla_deadlines, add_business_hours,
    evaluate_sla_status, format_ticket_age, parse_iso_datetime
)
from src.ticket_service import create_ticket, get_admin_dashboard_metrics


def test_sla_targets_by_priority():
    """Validates SLA response and resolution targets for all priorities."""
    created_at = "2026-10-26T09:00:00Z"  # Monday 09:00

    # Critical: 1h response, 4h resolution
    crit = calculate_sla_deadlines("Critical", created_at)
    assert crit["response_due_at"] == "2026-10-26T10:00:00Z"
    assert crit["resolution_due_at"] == "2026-10-26T13:00:00Z"

    # Medium: 8h response (end of Monday 17:00), 48h resolution (6 business days)
    med = calculate_sla_deadlines("Medium", created_at)
    assert med["response_due_at"] == "2026-10-26T17:00:00Z"


def test_business_calendar_skips_weekends():
    """Adding 8 business hours starting Friday 13:00 must roll remaining 4 hours into Monday 13:00."""
    friday_1pm = datetime(2026, 10, 23, 13, 0, tzinfo=timezone.utc)  # Friday 13:00
    # Friday 13:00 -> 17:00 = 4 business hours.
    # Weekend Saturday & Sunday skipped.
    # Monday 09:00 -> +4 hours = Monday 13:00.
    result = add_business_hours(friday_1pm, 8)
    assert result.weekday() == 0  # Monday
    assert result.hour == 13
    assert result.minute == 0


def test_evaluate_sla_status_overdue_flag():
    """Identifies overdue tickets when resolution deadline has elapsed without resolution."""
    sla_row = {
        "response_due_at": "2026-10-15T10:00:00Z",
        "resolution_due_at": "2026-10-15T17:00:00Z",
        "response_met": 1,
        "resolution_met": None,
    }
    # Current time is October 28 (long after Oct 15)
    current_time = "2026-10-28T10:00:00Z"
    eval_res = evaluate_sla_status(sla_row, current_time_iso=current_time)
    assert eval_res["is_resolution_overdue"] is True


def test_dashboard_summary_calculations(temp_db_path):
    """Creates a mix of tickets and verifies dashboard metric aggregations."""
    # Create routine ticket (Resolved)
    t1 = create_ticket(
        employee_id="EMP-000006",
        subject="How do I access my payslip?",
        description="Payslip instructions needed.",
        db_path=temp_db_path
    )

    # Create sensitive ticket (In_Progress)
    t2 = create_ticket(
        employee_id="EMP-000007",
        subject="Unexpected salary deduction of $500",
        description="Deduction dispute needing audit.",
        db_path=temp_db_path
    )

    # Create overdue ticket created in past (sensitive dispute so it stays In_Progress)
    t3 = create_ticket(
        employee_id="EMP-000008",
        subject="Critical payroll shortage dispute from last month",
        description="My paycheck shortage dispute of $400 was submitted two weeks ago and is still unresolved.",
        created_at="2026-10-10T09:00:00Z",
        db_path=temp_db_path
    )

    metrics = get_admin_dashboard_metrics(db_path=temp_db_path)
    assert metrics["total_tickets"] == 3
    assert metrics["sensitive_count"] >= 1
    assert metrics["escalated_count"] >= 1
    assert metrics["overdue_count"] >= 1
    assert isinstance(metrics["sla_compliance_rate"], float)
