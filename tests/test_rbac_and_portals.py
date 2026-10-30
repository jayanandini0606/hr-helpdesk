"""
Automated tests for Role-Based Access Control (RBAC), Employee Portal,
HR/Admin Portal, Ticket Isolation, and Confidential Internal Notes.
"""

import pytest
from app import app
from src.ticket_service import create_ticket, add_ticket_message, get_ticket


@pytest.fixture
def test_client(temp_db_path, monkeypatch):
    """Configures Flask test client using isolated temp database."""
    monkeypatch.setenv("DATABASE_PATH", str(temp_db_path))

    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"

    with app.test_client() as client:
        yield client


def test_portal_selection_page_renders_both_portals(test_client):
    """Landing page must render both Employee Portal and HR/Admin Portal options."""
    res = test_client.get("/login")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Employee Portal" in html
    assert "HR / Admin Portal" in html
    assert "Personal Dashboard" in html
    assert "Queue Reassignment" in html


def test_employee_login_and_dashboard_access(test_client):
    """Employee login sets session and grants access to /employee dashboard."""
    # Login as Employee
    login_res = test_client.post("/login", data={
        "role": "Employee",
        "user_id": "EMP-000006"
    }, follow_redirects=True)
    assert login_res.status_code == 200
    html = login_res.get_data(as_text=True)
    assert "Welcome, Ishaan Sharma 006" in html
    assert "EMP-000006" in html
    assert "Total Requests Submitted" in html
    assert "Submit New HR Request" in html


def test_employee_cannot_access_admin_dashboard(test_client):
    """Employees must be strictly blocked from accessing /admin dashboard."""
    # Set session as Employee
    with test_client.session_transaction() as sess:
        sess["role"] = "Employee"
        sess["user_id"] = "EMP-000006"
        sess["employee_id"] = "EMP-000006"

    # Attempt to access /admin
    res = test_client.get("/admin", follow_redirects=True)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Access Denied: Administrative privileges required" in html
    assert "Welcome, Ishaan Sharma 006" in html


def test_hr_partner_can_access_admin_dashboard(test_client):
    """HR Partner can access /admin dashboard with full metrics and controls."""
    # Login as HR Partner
    login_res = test_client.post("/login", data={
        "role_and_user": "HR Partner|EMP-000001"
    }, follow_redirects=True)
    assert login_res.status_code == 200
    html = login_res.get_data(as_text=True)
    assert "HR Helpdesk Administration &amp; SLA Dashboard" in html or "HR Helpdesk Administration & SLA Dashboard" in html
    assert "Total Tickets" in html
    assert "Sensitive" in html
    assert "Overdue SLAs" in html
    assert "SLA Rate" in html


def test_strict_employee_ticket_isolation(test_client, temp_db_path):
    """Employees must only be able to view tickets they personally submitted."""
    # Create ticket for EMP-000006
    t1 = create_ticket(
        employee_id="EMP-000006",
        subject="Ticket for Employee 6",
        description="Question regarding health benefits",
        db_path=temp_db_path
    )
    # Create ticket for EMP-000007
    t2 = create_ticket(
        employee_id="EMP-000007",
        subject="Ticket for Employee 7",
        description="Question regarding leave entitlement",
        db_path=temp_db_path
    )

    # Login as EMP-000006
    with test_client.session_transaction() as sess:
        sess["role"] = "Employee"
        sess["user_id"] = "EMP-000006"
        sess["employee_id"] = "EMP-000006"

    # EMP-000006 can view their own ticket
    res1 = test_client.get(f"/tickets/{t1['ticket_id']}", follow_redirects=True)
    assert res1.status_code == 200
    assert "Ticket for Employee 6" in res1.get_data(as_text=True)

    # EMP-000006 CANNOT view EMP-000007's ticket
    res2 = test_client.get(f"/tickets/{t2['ticket_id']}", follow_redirects=True)
    assert res2.status_code == 200
    html2 = res2.get_data(as_text=True)
    assert "Access Denied: Ticket" in html2
    assert "belongs to another employee" in html2


def test_internal_hr_notes_hidden_from_employee_portal(test_client, temp_db_path):
    """Confidential internal HR notes must NEVER appear in the employee portal."""
    # Create ticket for EMP-000006
    t = create_ticket(
        employee_id="EMP-000006",
        subject="Dispute inquiry",
        description="Inquiry regarding compensation calculation",
        db_path=temp_db_path
    )
    tid = t["ticket_id"]

    # HR Partner adds an internal note
    add_ticket_message(
        ticket_id=tid,
        sender_type="HR",
        message_text="[INTERNAL NOTE] Confidential HR investigation: supervisor interviewed, escalation pending.",
        message_type="Clarification",
        db_path=temp_db_path
    )

    # 1. As HR Partner: Note IS visible
    with test_client.session_transaction() as sess:
        sess["role"] = "HR Partner"
        sess["user_id"] = "EMP-000001"
        sess["employee_id"] = "EMP-000001"

    hr_res = test_client.get(f"/tickets/{tid}")
    hr_html = hr_res.get_data(as_text=True)
    assert "CONFIDENTIAL INTERNAL NOTE" in hr_html
    assert "supervisor interviewed, escalation pending" in hr_html

    # 2. As Employee (EMP-000006): Note is COMPLETELY OMITTED
    with test_client.session_transaction() as sess:
        sess["role"] = "Employee"
        sess["user_id"] = "EMP-000006"
        sess["employee_id"] = "EMP-000006"

    emp_res = test_client.get(f"/tickets/{tid}")
    emp_html = emp_res.get_data(as_text=True)
    assert "CONFIDENTIAL INTERNAL NOTE" not in emp_html
    assert "supervisor interviewed" not in emp_html


def test_employee_dashboard_search_and_filters(test_client, temp_db_path):
    """Employee dashboard filters tickets by search keyword, category, and priority."""
    # Create tickets
    create_ticket(
        employee_id="EMP-000006",
        subject="Medical Dental benefits claim",
        description="How to file dental claims?",
        user_category_id="CAT-BEN-001",
        db_path=temp_db_path
    )
    create_ticket(
        employee_id="EMP-000006",
        subject="Annual Vacation leave policy",
        description="How many vacation days per year?",
        user_category_id="CAT-LEV-002",
        db_path=temp_db_path
    )

    with test_client.session_transaction() as sess:
        sess["role"] = "Employee"
        sess["user_id"] = "EMP-000006"
        sess["employee_id"] = "EMP-000006"

    # Search filter
    res = test_client.get("/employee?search=Dental")
    html = res.get_data(as_text=True)
    assert "Medical Dental benefits claim" in html
    assert "Annual Vacation leave policy" not in html
