"""
AI-Powered HR Helpdesk — Flask Application.
Provides employee self-service portal, HR admin dashboard,
grounded policy management, SLA tracking, and ticket workflow lifecycle.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify

from src.database import query_all, query_one, get_db_path
from src.ticket_service import (
    create_ticket, get_ticket, add_ticket_message,
    reassign_ticket, update_ticket_status, list_tickets,
    get_admin_dashboard_metrics, seed_demo_scenarios
)
from src.policy_retrieval import get_all_policies_summary, get_current_iso_time
from src.generate_master_data import generate_master_data, CATEGORIES

PROJECT_ROOT = Path(__file__).resolve().parent

app = Flask(
    __name__,
    template_folder=str(PROJECT_ROOT / "templates"),
    static_folder=str(PROJECT_ROOT / "static")
)
app.secret_key = os.getenv("SECRET_KEY", "yottaflex-fde-demo-secret-key-2026")


# --------------------------------------------------
# Template Filters & Context Processors
# --------------------------------------------------

@app.template_filter("format_dt")
def format_datetime_filter(iso_str: str) -> str:
    if not iso_str:
        return "—"
    try:
        iso_clean = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_clean)
        return dt.strftime("%b %d, %Y %H:%M UTC")
    except Exception:
        return iso_str


@app.template_filter("status_badge")
def status_badge_filter(status: str) -> str:
    mapping = {
        "Open": "badge-open",
        "In_Progress": "badge-in-progress",
        "Awaiting_Employee": "badge-awaiting",
        "Resolved": "badge-resolved",
        "Closed": "badge-closed",
    }
    return mapping.get(status, "badge-default")


@app.template_filter("priority_badge")
def priority_badge_filter(priority: str) -> str:
    mapping = {
        "Critical": "badge-priority-critical",
        "High": "badge-priority-high",
        "Medium": "badge-priority-medium",
        "Low": "badge-priority-low",
    }
    return mapping.get(priority, "badge-default")


@app.context_processor
def inject_global_data():
    current_emp_id = session.get("employee_id", "EMP-000006")
    current_emp = query_one(
        "SELECT * FROM Employee WHERE employee_id = ?",
        (current_emp_id,)
    ) or {"employee_id": "EMP-000006", "full_name": "Aditi Reddy 006", "audience": "Employee"}

    employees = query_all("""
        SELECT employee_id, full_name, audience, department_id
        FROM Employee
        ORDER BY employee_id ASC
        LIMIT 25
    """)

    return {
        "current_employee": current_emp,
        "demo_employees": employees,
        "categories_list": CATEGORIES,
        "now_iso": get_current_iso_time()
    }


# --------------------------------------------------
# Routes: Portal & Employee Experience
# --------------------------------------------------

@app.route("/")
def index():
    return redirect(url_for("employee_home"))


@app.route("/employee")
def employee_home():
    emp_id = session.get("employee_id", "EMP-000006")
    employee = query_one("""
        SELECT e.*, d.department_name
        FROM Employee e
        JOIN Department d ON e.department_id = d.department_id
        WHERE e.employee_id = ?
    """, (emp_id,))

    tickets = list_tickets(filters={"employee_id": emp_id})

    # Stats for current employee
    total_tickets = len(tickets)
    resolved_tickets = sum(1 for t in tickets if t["status"] in ("Resolved", "Closed"))
    in_progress_tickets = sum(1 for t in tickets if t["status"] in ("Open", "In_Progress", "Awaiting_Employee"))

    return render_template(
        "employee_home.html",
        employee=employee,
        tickets=tickets,
        total_tickets=total_tickets,
        resolved_tickets=resolved_tickets,
        in_progress_tickets=in_progress_tickets
    )


@app.route("/employee/select", methods=["POST"])
def select_employee():
    emp_id = request.form.get("employee_id")
    if emp_id:
        session["employee_id"] = emp_id
        flash(f"Switched active demo employee to {emp_id}.", "info")
    return redirect(request.referrer or url_for("employee_home"))


@app.route("/tickets/new", methods=["GET", "POST"])
def new_ticket():
    emp_id = session.get("employee_id", "EMP-000006")

    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()
        category_id = request.form.get("category_id", "").strip() or None

        if not subject or not description:
            flash("Please enter both a subject and a description for your request.", "error")
            return render_template("new_ticket.html", subject=subject, description=description, category_id=category_id)

        if len(subject) > 250:
            flash("Subject is too long (maximum 250 characters).", "error")
            return render_template("new_ticket.html", subject=subject, description=description, category_id=category_id)

        try:
            result = create_ticket(
                employee_id=emp_id,
                subject=subject,
                description=description,
                user_category_id=category_id
            )
            flash(f"Ticket {result['ticket_id']} submitted successfully!", "success")
            return redirect(url_for("ticket_detail", ticket_id=result["ticket_id"]))
        except Exception as e:
            flash(f"Error creating ticket: {str(e)}", "error")
            return render_template("new_ticket.html", subject=subject, description=description, category_id=category_id)

    return render_template("new_ticket.html")


@app.route("/tickets/<ticket_id>")
def ticket_detail(ticket_id: str):
    ticket_bundle = get_ticket(ticket_id)
    if not ticket_bundle:
        abort(404, description=f"Ticket {ticket_id} was not found.")

    queues = ["Benefits", "Leave", "Payroll", "Onboarding", "HR-Confidential", "IT-Support", "HR-General"]

    return render_template(
        "ticket_detail.html",
        ticket=ticket_bundle["ticket"],
        messages=ticket_bundle["messages"],
        assignments=ticket_bundle["assignments"],
        current_assignment=ticket_bundle["current_assignment"],
        citations=ticket_bundle["citations"],
        resolution=ticket_bundle["resolution"],
        sla=ticket_bundle["sla"],
        sla_status=ticket_bundle["sla_status"],
        events=ticket_bundle["events"],
        ticket_age=ticket_bundle["ticket_age"],
        available_queues=queues
    )


@app.route("/tickets/<ticket_id>/message", methods=["POST"])
def post_ticket_message(ticket_id: str):
    sender_type = request.form.get("sender_type", "Employee")
    message_text = request.form.get("message_text", "").strip()
    message_type = request.form.get("message_type", "Clarification")

    if not message_text:
        flash("Message content cannot be blank.", "error")
        return redirect(url_for("ticket_detail", ticket_id=ticket_id))

    try:
        add_ticket_message(
            ticket_id=ticket_id,
            sender_type=sender_type,
            message_text=message_text,
            message_type=message_type
        )
        flash("Message added to conversation.", "success")
    except Exception as e:
        flash(f"Failed to post message: {str(e)}", "error")

    return redirect(url_for("ticket_detail", ticket_id=ticket_id))


@app.route("/tickets/<ticket_id>/reassign", methods=["POST"])
def admin_reassign(ticket_id: str):
    new_queue = request.form.get("new_queue", "").strip()
    new_assignee = request.form.get("new_assignee", "").strip() or None
    reason = request.form.get("reason", "").strip() or "Reassigned via admin console"

    if not new_queue:
        flash("Assigned queue is required.", "error")
        return redirect(url_for("ticket_detail", ticket_id=ticket_id))

    try:
        reassign_ticket(ticket_id, new_queue, new_assignee, reason)
        flash(f"Ticket reassigned to {new_queue}.", "success")
    except Exception as e:
        flash(f"Reassignment failed: {str(e)}", "error")

    return redirect(url_for("ticket_detail", ticket_id=ticket_id))


@app.route("/tickets/<ticket_id>/status", methods=["POST"])
def admin_status(ticket_id: str):
    new_status = request.form.get("status", "").strip()
    reason = request.form.get("reason", "").strip() or "Status updated via admin console"
    outcome = request.form.get("outcome", "").strip() or None
    summary = request.form.get("resolution_summary", "").strip() or None

    try:
        update_ticket_status(
            ticket_id=ticket_id,
            new_status=new_status,
            reason=reason,
            resolution_outcome=outcome,
            resolution_summary=summary
        )
        flash(f"Ticket status changed to {new_status}.", "success")
    except Exception as e:
        flash(f"Status update failed: {str(e)}", "error")

    return redirect(url_for("ticket_detail", ticket_id=ticket_id))


# --------------------------------------------------
# Routes: HR Admin Dashboard
# --------------------------------------------------

@app.route("/admin")
def admin_dashboard():
    # Filter parameters
    status = request.args.get("status")
    category_id = request.args.get("category_id")
    priority = request.args.get("priority")
    queue = request.args.get("queue")
    sensitive = request.args.get("sensitive")
    issue_type = request.args.get("issue_type")
    search = request.args.get("search")

    filters = {}
    if status:
        filters["status"] = status
    if category_id:
        filters["category_id"] = category_id
    if priority:
        filters["priority"] = priority
    if queue:
        filters["assigned_queue"] = queue
    if sensitive in ("0", "1"):
        filters["sensitive_flag"] = int(sensitive)
    if issue_type:
        filters["issue_type"] = issue_type
    if search:
        filters["search"] = search

    tickets = list_tickets(filters=filters)
    metrics = get_admin_dashboard_metrics()

    queues = ["Benefits", "Leave", "Payroll", "Onboarding", "HR-Confidential", "IT-Support", "HR-General"]

    return render_template(
        "admin_dashboard.html",
        tickets=tickets,
        metrics=metrics,
        filters=filters,
        available_queues=queues
    )


# --------------------------------------------------
# Routes: Policy Management
# --------------------------------------------------

@app.route("/policies")
def policy_list():
    as_of_date = request.args.get("as_of_date")
    policies = get_all_policies_summary(as_of_date=as_of_date)
    return render_template(
        "policy_list.html",
        policies=policies,
        selected_date=as_of_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )


# --------------------------------------------------
# Routes: Demo Tools & API Helpers
# --------------------------------------------------

@app.route("/admin/seed-demo", methods=["POST"])
def seed_demo_route():
    try:
        results = seed_demo_scenarios()
        flash(f"Successfully seeded {len(results)} interview demo scenarios!", "success")
    except Exception as e:
        flash(f"Error seeding demo scenarios: {str(e)}", "error")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/reset-db", methods=["POST"])
def reset_db_route():
    try:
        generate_master_data()
        flash("Master database reset and generated with 100% integrity!", "success")
    except Exception as e:
        flash(f"Database reset error: {str(e)}", "error")
    return redirect(url_for("admin_dashboard"))


# --------------------------------------------------
# Error Handlers
# --------------------------------------------------

@app.errorhandler(404)
def not_found_error(error):
    return render_template("base.html", error_message="The requested page or ticket could not be found (404)."), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template("base.html", error_message="An internal server error occurred (500). Please check application logs."), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
