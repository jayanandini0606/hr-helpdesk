"""
AI-Powered HR Helpdesk — Flask Application.
Provides role-based interfaces with separate Employee and HR/Admin portals,
grounded policy retrieval, SLA tracking, sensitive case routing, and audit trails.
"""

import os
from functools import wraps
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, abort, jsonify
)

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
# User Session & RBAC Helpers
# --------------------------------------------------

def get_current_user() -> Dict[str, Any]:
    """Retrieves current session identity and employee master data."""
    role = session.get("role", "Employee")
    user_id = session.get("user_id") or session.get("employee_id", "EMP-000006")

    emp = query_one("""
        SELECT e.*, d.department_name
        FROM Employee e
        LEFT JOIN Department d ON e.department_id = d.department_id
        WHERE e.employee_id = ?
    """, (user_id,))

    if not emp:
        emp = {
            "employee_id": user_id,
            "full_name": "Ishaan Sharma 006",
            "department_id": "DPT-001",
            "department_name": "Human Resources",
            "employment_status": "Active",
            "audience": "Employee"
        }

    # Synchronize session keys
    session["role"] = role
    session["user_id"] = user_id
    session["employee_id"] = user_id

    return {
        **emp,
        "role": role
    }


def admin_required(f):
    """Restricts route to authorized HR Partner, IT Partner, or Admin roles."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = get_current_user()
        if current_user.get("role") == "Employee":
            flash("Access Denied: Administrative privileges required. Redirected to Employee Portal.", "error")
            return redirect(url_for("employee_home"))
        return f(*args, **kwargs)
    return decorated_function


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
    current_user = get_current_user()

    employees = query_all("""
        SELECT e.employee_id, e.full_name, e.audience, e.department_id, d.department_name
        FROM Employee e
        LEFT JOIN Department d ON e.department_id = d.department_id
        ORDER BY e.employee_id ASC
        LIMIT 30
    """)

    return {
        "current_user": current_user,
        "current_employee": current_user,
        "demo_employees": employees,
        "categories_list": CATEGORIES,
        "now_iso": get_current_iso_time()
    }


# --------------------------------------------------
# Routes: Landing & Role Selection
# --------------------------------------------------

@app.route("/")
def index():
    """Landing route: redirects active sessions to portal, or to role selector."""
    if "role" not in session:
        return redirect(url_for("portal_select_route"))
    if session.get("role") == "Employee":
        return redirect(url_for("employee_home"))
    return redirect(url_for("admin_dashboard"))


@app.route("/portal-select")
@app.route("/login", methods=["GET", "POST"])
def portal_select_route():
    """Role selection & login landing page with separate Employee and HR/Admin options."""
    if request.method == "POST":
        role = request.form.get("role")
        user_id = request.form.get("user_id")
        role_and_user = request.form.get("role_and_user")

        if role_and_user:
            parts = role_and_user.split("|")
            if len(parts) == 2:
                role = parts[0]
                user_id = parts[1]

        role = role or "Employee"
        user_id = user_id or "EMP-000006"

        session["role"] = role
        session["user_id"] = user_id
        session["employee_id"] = user_id

        flash(f"Entered as {role} ({user_id}).", "success")
        if role == "Employee":
            return redirect(url_for("employee_home"))
        else:
            return redirect(url_for("admin_dashboard"))

    # GET: render landing page
    current_user = get_current_user()
    employee_options = query_all("""
        SELECT e.employee_id, e.full_name, e.department_id, d.department_name
        FROM Employee e
        LEFT JOIN Department d ON e.department_id = d.department_id
        ORDER BY e.employee_id ASC
        LIMIT 30
    """)
    return render_template(
        "portal_select.html",
        employee_options=employee_options,
        current_user=current_user
    )


@app.route("/logout")
def logout_route():
    """Clears active session and returns to portal selection landing page."""
    session.clear()
    flash("You have been signed out of your portal session.", "info")
    return redirect(url_for("portal_select_route"))


@app.route("/employee/select", methods=["POST"])
def select_employee():
    """Demo switcher to quickly change active employee identity."""
    emp_id = request.form.get("employee_id")
    if emp_id:
        session["user_id"] = emp_id
        session["employee_id"] = emp_id
        flash(f"Switched active demo employee to {emp_id}.", "info")
    return redirect(request.referrer or url_for("employee_home"))


# --------------------------------------------------
# Routes: Employee Portal Experience
# --------------------------------------------------

@app.route("/employee")
def employee_home():
    """Employee Portal Dashboard: personalized metrics, filterable ticket list."""
    current_user = get_current_user()
    emp_id = current_user["employee_id"]

    employee = query_one("""
        SELECT e.*, d.department_name
        FROM Employee e
        LEFT JOIN Department d ON e.department_id = d.department_id
        WHERE e.employee_id = ?
    """, (emp_id,))

    # Parse search and filter parameters
    status = request.args.get("status")
    category_id = request.args.get("category_id")
    priority = request.args.get("priority")
    search = request.args.get("search")

    filters = {"employee_id": emp_id}
    filter_inputs = {}
    if status:
        filters["status"] = status
        filter_inputs["status"] = status
    if category_id:
        filters["category_id"] = category_id
        filter_inputs["category_id"] = category_id
    if priority:
        filters["priority"] = priority
        filter_inputs["priority"] = priority
    if search:
        filters["search"] = search
        filter_inputs["search"] = search

    tickets = list_tickets(filters=filters)

    # Aggregate stats for this specific employee across all their tickets
    all_emp_tickets = list_tickets(filters={"employee_id": emp_id, "limit": 1000})
    total_tickets = len(all_emp_tickets)
    resolved_tickets = sum(1 for t in all_emp_tickets if t["status"] in ("Resolved", "Closed"))
    open_tickets = sum(1 for t in all_emp_tickets if t["status"] in ("Open", "In_Progress", "Awaiting_Employee"))

    return render_template(
        "employee_home.html",
        employee=employee,
        tickets=tickets,
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        resolved_tickets=resolved_tickets,
        filters=filter_inputs
    )


@app.route("/tickets/new", methods=["GET", "POST"])
def new_ticket():
    """Ticket intake: saves ticket, classifies, checks sensitive rules, grounds answer, routes."""
    current_user = get_current_user()
    emp_id = current_user["employee_id"]

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


# --------------------------------------------------
# Routes: Ticket Detail & Message Lifecycle
# --------------------------------------------------

@app.route("/tickets/<ticket_id>")
def ticket_detail(ticket_id: str):
    """Detailed view of ticket, conversation, policy citations, SLA, and audit events."""
    ticket_bundle = get_ticket(ticket_id)
    if not ticket_bundle:
        abort(404, description=f"Ticket {ticket_id} was not found.")

    current_user = get_current_user()

    # Strict isolation: Employees can only view tickets they personally submitted
    if current_user.get("role") == "Employee":
        if ticket_bundle["ticket"]["employee_id"] != current_user["employee_id"]:
            flash(f"Access Denied: Ticket {ticket_id} belongs to another employee. You can only view your own submitted requests.", "error")
            return redirect(url_for("employee_home"))

    # Process messages: strictly hide internal notes from employee portal
    raw_messages = ticket_bundle["messages"]
    processed_messages = []
    for msg in raw_messages:
        text = msg.get("message_text", "")
        is_internal = text.startswith("[INTERNAL NOTE]")

        # Employees must never see internal staff notes
        if current_user.get("role") == "Employee" and is_internal:
            continue

        clean_text = text.replace("[INTERNAL NOTE]", "").strip() if is_internal else text
        msg_dict = dict(msg)
        msg_dict["is_internal_note"] = is_internal
        msg_dict["clean_text"] = clean_text
        processed_messages.append(msg_dict)

    queues = ["Benefits", "Leave", "Payroll", "Onboarding", "HR-Confidential", "IT-Support", "HR-General"]

    return render_template(
        "ticket_detail.html",
        ticket=ticket_bundle["ticket"],
        messages=processed_messages,
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
    """Appends conversation message or confidential internal note."""
    ticket_bundle = get_ticket(ticket_id)
    if not ticket_bundle:
        abort(404, description=f"Ticket {ticket_id} was not found.")

    current_user = get_current_user()

    # Employee ticket ownership verification
    if current_user.get("role") == "Employee":
        if ticket_bundle["ticket"]["employee_id"] != current_user["employee_id"]:
            flash("Access Denied: You cannot message on another employee's ticket.", "error")
            return redirect(url_for("employee_home"))

    message_text = request.form.get("message_text", "").strip()
    if not message_text:
        flash("Message content cannot be blank.", "error")
        return redirect(url_for("ticket_detail", ticket_id=ticket_id))

    is_internal_note = request.form.get("is_internal_note", "0") == "1"

    if current_user.get("role") == "Employee":
        sender_type = "Employee"
        message_type = "Clarification"
        final_text = message_text
    else:
        # HR / Admin staff
        sender_type = "HR"
        message_type = "Clarification"
        if is_internal_note:
            final_text = f"[INTERNAL NOTE] {message_text}"
        else:
            final_text = message_text

    try:
        add_ticket_message(
            ticket_id=ticket_id,
            sender_type=sender_type,
            message_text=final_text,
            message_type=message_type
        )
        if is_internal_note:
            flash("Confidential internal note saved. (Hidden from employee portal)", "info")
        else:
            flash("Message added to conversation.", "success")
    except Exception as e:
        flash(f"Failed to post message: {str(e)}", "error")

    return redirect(url_for("ticket_detail", ticket_id=ticket_id))


@app.route("/tickets/<ticket_id>/reassign", methods=["POST"])
@admin_required
def admin_reassign(ticket_id: str):
    """Reassigns ticket queue and updates assignment history."""
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
@admin_required
def admin_status(ticket_id: str):
    """Updates ticket status, records outcome and resolution summary."""
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
@admin_required
def admin_dashboard():
    """HR / Admin operations dashboard with KPI metrics, filters, and ticket table."""
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
    """Versioned policy documents, effective dates, and published knowledge articles."""
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
@admin_required
def seed_demo_route():
    try:
        results = seed_demo_scenarios()
        flash(f"Successfully seeded {len(results)} interview demo scenarios!", "success")
    except Exception as e:
        flash(f"Error seeding demo scenarios: {str(e)}", "error")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/reset-db", methods=["POST"])
@admin_required
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

@app.errorhandler(403)
def forbidden_error(error):
    return render_template("base.html", error_message="Access Denied (403): You do not have permission to view this resource."), 403


@app.errorhandler(404)
def not_found_error(error):
    return render_template("base.html", error_message="The requested page or ticket could not be found (404)."), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template("base.html", error_message="An internal server error occurred (500). Please check application logs."), 500


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )
