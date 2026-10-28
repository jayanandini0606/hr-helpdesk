"""
Ticket lifecycle and workflow service for AI-Powered HR Helpdesk.
Implements the complete ticket lifecycle: creation, classification,
SLA calculation, grounded retrieval, message generation, assignment history,
status transitions, and event auditing.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import uuid

from src.database import get_connection, db_session, query_all, query_one
from src.classifier import classify_request
from src.policy_retrieval import retrieve_relevant_knowledge, get_current_iso_time, get_current_iso_date
from src.sla_service import calculate_sla_deadlines, evaluate_sla_status, format_ticket_age
from src.response_service import generate_ticket_response


def generate_ticket_id(conn) -> str:
    """Generates next ticket identifier formatted as TKT-2026-XXXXXX."""
    row = conn.execute("SELECT COUNT(*) FROM Ticket").fetchone()
    count = (row[0] if row else 0) + 1
    return f"TKT-2026-{count:06d}"


def create_ticket(
    employee_id: str,
    subject: str,
    description: str,
    user_category_id: Optional[str] = None,
    created_at: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Creates and processes a new ticket end-to-end.
    """
    now_iso = created_at or get_current_iso_time()
    now_date = now_iso.split("T")[0]

    with db_session(db_path) as conn:
        # 1. Validate employee
        emp = conn.execute("SELECT * FROM Employee WHERE employee_id = ?", (employee_id,)).fetchone()
        if not emp:
            raise ValueError(f"Employee {employee_id} does not exist.")

        # 2. Run Classification & Sensitive Case Detection
        classification = classify_request(subject, description, user_category_id=user_category_id)
        category_id = classification["category_id"]
        priority = classification["priority"]
        sensitive_flag = classification["sensitive_flag"]
        assigned_queue = classification["assigned_queue"]
        routing_reason = classification["routing_reason"]

        ticket_id = generate_ticket_id(conn)

        # Initial status: 'Open'
        initial_status = "Open"
        conn.execute("""
            INSERT INTO Ticket (
                ticket_id, employee_id, category_id, subject, description,
                status, priority, sensitive_flag, issue_type, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket_id, employee_id, category_id, subject, description,
            initial_status, priority, sensitive_flag,
            ", ".join(classification.get("sensitive_types", [])) or "Standard",
            now_iso, now_iso
        ))

        # 3. Save initial employee message
        msg_emp_id = f"MSG-{ticket_id}-001"
        conn.execute("""
            INSERT INTO Message (
                message_id, ticket_id, sequence_number, sender_type,
                message_text, message_type, created_at
            ) VALUES (?, ?, 1, 'Employee', ?, 'Request', ?)
        """, (msg_emp_id, ticket_id, description, now_iso))

        # 4. Save assignment record
        assignment_id = f"ASG-{ticket_id}-001"
        conn.execute("""
            INSERT INTO Assignment (
                assignment_id, ticket_id, assigned_queue, assigned_to,
                reason, assigned_at, ended_at
            ) VALUES (?, ?, ?, NULL, ?, ?, NULL)
        """, (assignment_id, ticket_id, assigned_queue, routing_reason, now_iso))

        # 5. Calculate SLA deadlines
        sla_data = calculate_sla_deadlines(priority, now_iso)
        sla_id = f"SLA-{ticket_id}"
        # Response is delivered immediately by Assistant, so response_met = 1
        conn.execute("""
            INSERT INTO SLA (
                sla_id, ticket_id, policy_name, response_due_at, resolution_due_at,
                business_calendar, response_met, resolution_met
            ) VALUES (?, ?, ?, ?, ?, ?, 1, NULL)
        """, (
            sla_id, ticket_id, sla_data["policy_name"],
            sla_data["response_due_at"], sla_data["resolution_due_at"],
            sla_data["business_calendar"]
        ))

        # 6. Record creation event
        event_1_id = f"EVT-{ticket_id}-001"
        conn.execute("""
            INSERT INTO TicketEvent (
                event_id, ticket_id, old_status, new_status, reason, occurred_at
            ) VALUES (?, ?, NULL, 'Open', 'Ticket created by employee', ?)
        """, (event_1_id, ticket_id, now_iso))

        # 7. Knowledge retrieval and response generation
        retrieved_articles = []
        if sensitive_flag == 0:
            retrieved_articles = retrieve_relevant_knowledge(
                query_text=f"{subject} {description}",
                category_id=category_id,
                as_of_date=now_date,
                db_path=db_path
            )

        response_payload = generate_ticket_response(
            ticket_id=ticket_id,
            subject=subject,
            description=description,
            classification=classification,
            retrieved_articles=retrieved_articles
        )

        # 8. Record assistant response message
        msg_asst_id = f"MSG-{ticket_id}-002"
        conn.execute("""
            INSERT INTO Message (
                message_id, ticket_id, sequence_number, sender_type,
                message_text, message_type, created_at
            ) VALUES (?, ?, 2, 'Assistant', ?, ?, ?)
        """, (
            msg_asst_id, ticket_id,
            response_payload["message_text"],
            response_payload["message_type"],
            now_iso
        ))

        # 9. Store policy citations if applicable
        citations = response_payload.get("citations", [])
        for cit in citations:
            conn.execute("""
                INSERT OR IGNORE INTO TicketPolicyCitation (
                    ticket_id, version_id, article_id, cited_at
                ) VALUES (?, ?, ?, ?)
            """, (ticket_id, cit["version_id"], cit.get("article_id"), now_iso))

        # 10. Handle outcome, ticket status update, and resolution
        outcome = response_payload["outcome"]
        summary = response_payload["resolution_summary"]

        if sensitive_flag == 1:
            # Sensitive case: escalated to human team, status becomes 'In_Progress'
            final_status = "In_Progress"
            conn.execute("""
                UPDATE Ticket SET status = ?, updated_at = ? WHERE ticket_id = ?
            """, (final_status, now_iso, ticket_id))

            conn.execute("""
                INSERT INTO Resolution (
                    resolution_id, ticket_id, outcome, resolution_summary,
                    resolved_at, article_id, version_id
                ) VALUES (?, ?, 'Escalated', ?, NULL, NULL, NULL)
            """, (f"RES-{ticket_id}", ticket_id, summary))

            conn.execute("""
                INSERT INTO TicketEvent (
                    event_id, ticket_id, old_status, new_status, reason, occurred_at
                ) VALUES (?, ?, 'Open', 'In_Progress', ?, ?)
            """, (f"EVT-{ticket_id}-002", ticket_id, f"Escalated to queue '{assigned_queue}': {routing_reason}", now_iso))

        elif outcome == "Answered":
            # Routine grounded answer: resolved automatically
            final_status = "Resolved"
            conn.execute("""
                UPDATE Ticket SET status = ?, updated_at = ? WHERE ticket_id = ?
            """, (final_status, now_iso, ticket_id))

            conn.execute("""
                INSERT INTO Resolution (
                    resolution_id, ticket_id, outcome, resolution_summary,
                    resolved_at, article_id, version_id
                ) VALUES (?, ?, 'Answered', ?, ?, ?, ?)
            """, (
                f"RES-{ticket_id}", ticket_id, summary, now_iso,
                response_payload.get("primary_article_id"),
                response_payload.get("primary_version_id")
            ))

            # Resolution SLA met!
            conn.execute("""
                UPDATE SLA SET resolution_met = 1 WHERE ticket_id = ?
            """, (ticket_id,))

            conn.execute("""
                INSERT INTO TicketEvent (
                    event_id, ticket_id, old_status, new_status, reason, occurred_at
                ) VALUES (?, ?, 'Open', 'Resolved', 'Automated grounded resolution provided with policy citations', ?)
            """, (f"EVT-{ticket_id}-002", ticket_id, now_iso))

        else:
            # Routine but ungrounded / missing policy: set to In_Progress for human review
            final_status = "In_Progress"
            conn.execute("""
                UPDATE Ticket SET status = ?, updated_at = ? WHERE ticket_id = ?
            """, (final_status, now_iso, ticket_id))

            conn.execute("""
                INSERT INTO Resolution (
                    resolution_id, ticket_id, outcome, resolution_summary,
                    resolved_at, article_id, version_id
                ) VALUES (?, ?, 'Unresolved', ?, NULL, NULL, NULL)
            """, (f"RES-{ticket_id}", ticket_id, summary))

            conn.execute("""
                INSERT INTO TicketEvent (
                    event_id, ticket_id, old_status, new_status, reason, occurred_at
                ) VALUES (?, ?, 'Open', 'In_Progress', 'No matching policy found; routed for human clarification', ?)
            """, (f"EVT-{ticket_id}-002", ticket_id, now_iso))

        return {
            "ticket_id": ticket_id,
            "status": final_status,
            "category_id": category_id,
            "category_name": classification["category_name"],
            "priority": priority,
            "sensitive_flag": sensitive_flag,
            "assigned_queue": assigned_queue,
            "routing_reason": routing_reason,
            "outcome": outcome,
            "assistant_message": response_payload["message_text"],
            "citations": citations,
        }


def get_ticket(ticket_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retrieves complete ticket bundle including messages, assignments, citations, SLA, and events."""
    ticket = query_one("""
        SELECT t.*, e.full_name as employee_name, e.department_id as employee_department,
               c.category_name, c.default_queue as category_queue
        FROM Ticket t
        JOIN Employee e ON t.employee_id = e.employee_id
        JOIN Category c ON t.category_id = c.category_id
        WHERE t.ticket_id = ?
    """, (ticket_id,), db_path=db_path)

    if not ticket:
        return None

    # Fetch messages
    messages = query_all("""
        SELECT * FROM Message WHERE ticket_id = ? ORDER BY sequence_number ASC
    """, (ticket_id,), db_path=db_path)

    # Fetch assignments
    assignments = query_all("""
        SELECT * FROM Assignment WHERE ticket_id = ? ORDER BY assigned_at ASC
    """, (ticket_id,), db_path=db_path)

    # Fetch citations
    citations = query_all("""
        SELECT tpc.cited_at, pv.version_id, pv.version_number, pv.policy_text,
               pd.policy_id, pd.title as policy_title,
               ka.article_id, ka.title as article_title, ka.snippet
        FROM TicketPolicyCitation tpc
        JOIN PolicyVersion pv ON tpc.version_id = pv.version_id
        JOIN PolicyDocument pd ON pv.policy_id = pd.policy_id
        LEFT JOIN KnowledgeArticle ka ON tpc.article_id = ka.article_id
        WHERE tpc.ticket_id = ?
        ORDER BY tpc.cited_at ASC
    """, (ticket_id,), db_path=db_path)

    # Fetch resolution
    resolution = query_one("SELECT * FROM Resolution WHERE ticket_id = ?", (ticket_id,), db_path=db_path)

    # Fetch SLA
    sla = query_one("SELECT * FROM SLA WHERE ticket_id = ?", (ticket_id,), db_path=db_path)
    sla_eval = {}
    if sla:
        sla_eval = evaluate_sla_status(
            sla_row=sla,
            first_response_time_iso=messages[1]["created_at"] if len(messages) > 1 else None,
            resolved_time_iso=resolution["resolved_at"] if resolution and resolution.get("resolved_at") else None
        )

    # Fetch events
    events = query_all("""
        SELECT * FROM TicketEvent WHERE ticket_id = ? ORDER BY occurred_at ASC
    """, (ticket_id,), db_path=db_path)

    current_assignment = assignments[-1] if assignments else None

    return {
        "ticket": ticket,
        "messages": messages,
        "assignments": assignments,
        "current_assignment": current_assignment,
        "citations": citations,
        "resolution": resolution,
        "sla": sla,
        "sla_status": sla_eval,
        "events": events,
        "ticket_age": format_ticket_age(ticket["created_at"]),
    }


def add_ticket_message(
    ticket_id: str,
    sender_type: str,
    message_text: str,
    message_type: str = "Clarification",
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Appends a new message to a ticket and updates ticket timestamp."""
    now_iso = get_current_iso_time()
    with db_session(db_path) as conn:
        seq_row = conn.execute(
            "SELECT COALESCE(MAX(sequence_number), 0) FROM Message WHERE ticket_id = ?",
            (ticket_id,)
        ).fetchone()
        next_seq = (seq_row[0] if seq_row else 0) + 1
        msg_id = f"MSG-{ticket_id}-{next_seq:03d}"

        conn.execute("""
            INSERT INTO Message (
                message_id, ticket_id, sequence_number, sender_type,
                message_text, message_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (msg_id, ticket_id, next_seq, sender_type, message_text, message_type, now_iso))

        conn.execute("""
            UPDATE Ticket SET updated_at = ? WHERE ticket_id = ?
        """, (now_iso, ticket_id))

        return {"message_id": msg_id, "sequence_number": next_seq, "created_at": now_iso}


def reassign_ticket(
    ticket_id: str,
    new_queue: str,
    new_assignee: Optional[str],
    reason: str,
    db_path: Optional[Path] = None
) -> bool:
    """Closes current assignment and creates a new assignment record preserving history."""
    now_iso = get_current_iso_time()
    with db_session(db_path) as conn:
        # Close open assignments
        conn.execute("""
            UPDATE Assignment SET ended_at = ? WHERE ticket_id = ? AND ended_at IS NULL
        """, (now_iso, ticket_id))

        # Add new assignment
        count = conn.execute("SELECT COUNT(*) FROM Assignment WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] + 1
        asg_id = f"ASG-{ticket_id}-{count:03d}"
        conn.execute("""
            INSERT INTO Assignment (
                assignment_id, ticket_id, assigned_queue, assigned_to, reason, assigned_at, ended_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL)
        """, (asg_id, ticket_id, new_queue, new_assignee, reason, now_iso))

        # Log event
        conn.execute("""
            INSERT INTO TicketEvent (
                event_id, ticket_id, old_status, new_status, reason, occurred_at
            ) VALUES (?, ?, NULL, (SELECT status FROM Ticket WHERE ticket_id = ?), ?, ?)
        """, (f"EVT-{ticket_id}-{uuid.uuid4().hex[:6]}", ticket_id, ticket_id, f"Reassigned to {new_queue}: {reason}", now_iso))

        conn.execute("UPDATE Ticket SET updated_at = ? WHERE ticket_id = ?", (now_iso, ticket_id))
        return True


def update_ticket_status(
    ticket_id: str,
    new_status: str,
    reason: str,
    resolution_outcome: Optional[str] = None,
    resolution_summary: Optional[str] = None,
    db_path: Optional[Path] = None
) -> bool:
    """Validates status transition and updates resolution & SLA state."""
    allowed_statuses = {'Open', 'Awaiting_Employee', 'In_Progress', 'Resolved', 'Closed'}
    if new_status not in allowed_statuses:
        raise ValueError(f"Invalid status: {new_status}. Allowed: {allowed_statuses}")

    now_iso = get_current_iso_time()
    with db_session(db_path) as conn:
        curr = conn.execute("SELECT status FROM Ticket WHERE ticket_id = ?", (ticket_id,)).fetchone()
        if not curr:
            return False
        old_status = curr[0]

        conn.execute("UPDATE Ticket SET status = ?, updated_at = ? WHERE ticket_id = ?", (new_status, now_iso, ticket_id))

        # Log event
        evt_id = f"EVT-{ticket_id}-{uuid.uuid4().hex[:6]}"
        conn.execute("""
            INSERT INTO TicketEvent (event_id, ticket_id, old_status, new_status, reason, occurred_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (evt_id, ticket_id, old_status, new_status, reason, now_iso))

        # Handle Resolution & SLA if resolved/closed
        if new_status in ("Resolved", "Closed"):
            res = conn.execute("SELECT * FROM Resolution WHERE ticket_id = ?", (ticket_id,)).fetchone()
            outcome = resolution_outcome or ("Answered" if old_status == "Open" else "Escalated")
            summary = resolution_summary or f"Ticket marked as {new_status}: {reason}"

            if res:
                conn.execute("""
                    UPDATE Resolution SET outcome = ?, resolution_summary = ?, resolved_at = ?
                    WHERE ticket_id = ?
                """, (outcome, summary, now_iso, ticket_id))
            else:
                conn.execute("""
                    INSERT INTO Resolution (
                        resolution_id, ticket_id, outcome, resolution_summary, resolved_at, article_id, version_id
                    ) VALUES (?, ?, ?, ?, ?, NULL, NULL)
                """, (f"RES-{ticket_id}", ticket_id, outcome, summary, now_iso))

            # Evaluate SLA resolution met
            sla = conn.execute("SELECT resolution_due_at FROM SLA WHERE ticket_id = ?", (ticket_id,)).fetchone()
            if sla:
                resolution_met = 1 if now_iso <= sla[0] else 0
                conn.execute("UPDATE SLA SET resolution_met = ? WHERE ticket_id = ?", (resolution_met, ticket_id))

        return True


def list_tickets(
    filters: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Lists tickets with joined metadata and SLA status, supporting flexible filters."""
    filters = filters or {}
    conditions = []
    params = []

    if filters.get("status"):
        conditions.append("t.status = ?")
        params.append(filters["status"])

    if filters.get("category_id"):
        conditions.append("t.category_id = ?")
        params.append(filters["category_id"])

    if filters.get("priority"):
        conditions.append("t.priority = ?")
        params.append(filters["priority"])

    if filters.get("sensitive_flag") is not None:
        conditions.append("t.sensitive_flag = ?")
        params.append(int(filters["sensitive_flag"]))

    if filters.get("issue_type"):
        conditions.append("t.issue_type = ?")
        params.append(filters["issue_type"])

    if filters.get("employee_id"):
        conditions.append("t.employee_id = ?")
        params.append(filters["employee_id"])

    if filters.get("assigned_queue"):
        conditions.append("a.assigned_queue = ?")
        params.append(filters["assigned_queue"])

    if filters.get("search"):
        search_term = f"%{filters['search']}%"
        conditions.append("(t.ticket_id LIKE ? OR t.subject LIKE ? OR t.description LIKE ? OR e.full_name LIKE ?)")
        params.extend([search_term, search_term, search_term, search_term])

    limit = filters.get("limit", 100)
    limit_clause = f"LIMIT {int(limit)}" if limit else ""

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    sql = f"""
        SELECT t.*, e.full_name as employee_name, c.category_name,
               a.assigned_queue, a.assigned_to,
               s.response_due_at, s.resolution_due_at, s.response_met, s.resolution_met,
               r.outcome as resolution_outcome
        FROM Ticket t
        JOIN Employee e ON t.employee_id = e.employee_id
        JOIN Category c ON t.category_id = c.category_id
        LEFT JOIN (
            SELECT a1.*
            FROM Assignment a1
            JOIN (
                SELECT ticket_id, MAX(assigned_at) as max_at
                FROM Assignment
                GROUP BY ticket_id
            ) a2 ON a1.ticket_id = a2.ticket_id AND a1.assigned_at = a2.max_at
        ) a ON t.ticket_id = a.ticket_id
        LEFT JOIN SLA s ON t.ticket_id = s.ticket_id
        LEFT JOIN Resolution r ON t.ticket_id = r.ticket_id
        {where_clause}
        ORDER BY t.created_at DESC
        {limit_clause}
    """

    rows = query_all(sql, tuple(params), db_path=db_path)
    now_iso = get_current_iso_time()

    results = []
    for row in rows:
        item = dict(row)
        item["age"] = format_ticket_age(item["created_at"], now_iso)

        # Check overdue flags
        is_overdue = False
        if item.get("resolution_due_at") and item.get("status") not in ("Resolved", "Closed"):
            if now_iso > item["resolution_due_at"]:
                is_overdue = True
        item["is_overdue"] = is_overdue

        results.append(item)

    return results


def get_admin_dashboard_metrics(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Computes operational KPIs, SLA compliance rates, and queue distributions."""
    now_iso = get_current_iso_time()

    total_tickets = query_one("SELECT COUNT(*) as count FROM Ticket", db_path=db_path)["count"]

    # Status counts
    status_rows = query_all("""
        SELECT status, COUNT(*) as count FROM Ticket GROUP BY status
    """, db_path=db_path)
    status_counts = {r["status"]: r["count"] for r in status_rows}

    # Sensitive & Escalated
    sensitive_count = query_one(
        "SELECT COUNT(*) as count FROM Ticket WHERE sensitive_flag = 1",
        db_path=db_path
    )["count"]

    escalated_count = query_one(
        "SELECT COUNT(*) as count FROM Resolution WHERE outcome = 'Escalated'",
        db_path=db_path
    )["count"]

    # Overdue tickets count (open tickets past resolution_due_at)
    overdue_count = query_one("""
        SELECT COUNT(*) as count
        FROM Ticket t
        JOIN SLA s ON t.ticket_id = s.ticket_id
        WHERE t.status NOT IN ('Resolved', 'Closed')
          AND s.resolution_due_at < ?
    """, (now_iso,), db_path=db_path)["count"]

    # SLA Performance
    resolved_tickets = query_all("""
        SELECT s.resolution_met, s.response_met
        FROM SLA s
        JOIN Ticket t ON s.ticket_id = t.ticket_id
        WHERE t.status IN ('Resolved', 'Closed')
    """, db_path=db_path)

    total_resolved = len(resolved_tickets)
    met_count = sum(1 for r in resolved_tickets if r["resolution_met"] == 1)
    sla_compliance_rate = round((met_count / total_resolved * 100), 1) if total_resolved > 0 else 100.0

    # Category distribution
    cat_distribution = query_all("""
        SELECT c.category_name, COUNT(t.ticket_id) as count
        FROM Category c
        LEFT JOIN Ticket t ON c.category_id = t.category_id
        GROUP BY c.category_name
        ORDER BY count DESC
    """, db_path=db_path)

    # Queue distribution
    queue_distribution = query_all("""
        SELECT a.assigned_queue, COUNT(DISTINCT a.ticket_id) as count
        FROM Assignment a
        WHERE a.ended_at IS NULL
        GROUP BY a.assigned_queue
        ORDER BY count DESC
    """, db_path=db_path)

    # Recent activity
    recent_events = query_all("""
        SELECT te.*, t.subject
        FROM TicketEvent te
        JOIN Ticket t ON te.ticket_id = t.ticket_id
        ORDER BY te.occurred_at DESC
        LIMIT 10
    """, db_path=db_path)

    return {
        "total_tickets": total_tickets,
        "status_counts": status_counts,
        "sensitive_count": sensitive_count,
        "escalated_count": escalated_count,
        "overdue_count": overdue_count,
        "sla_compliance_rate": sla_compliance_rate,
        "category_distribution": cat_distribution,
        "queue_distribution": queue_distribution,
        "recent_events": recent_events,
    }


def seed_demo_scenarios(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Seeds the 6 core interview demo scenarios required by the challenge specification:
    1. Routine payslip access -> Grounded answer with citations (Resolved)
    2. Salary deduction dispute -> Sensitive payroll routing (In_Progress)
    3. Harassment complaint -> Confidential HR escalation (Critical, In_Progress)
    4. Unavailable policy (paid sabbatical) -> Unresolved clarification (In_Progress)
    5. Versioned policy selection demonstration
    6. Overdue SLA ticket demonstration
    """
    results = []

    # Scenario 1: Payslip access (Grounded routine resolution)
    s1 = create_ticket(
        employee_id="EMP-000006",
        subject="How do I access my monthly payslip?",
        description="I am looking for guidance on where to view and download my monthly salary payslips.",
        db_path=db_path
    )
    results.append({"scenario": "1. Grounded Routine Payslip Access", "ticket_id": s1["ticket_id"], "status": s1["status"]})

    # Scenario 2: Unexpected salary deduction (Sensitive payroll dispute)
    s2 = create_ticket(
        employee_id="EMP-000007",
        subject="Unexpected deduction in my monthly salary",
        description="There is an unexpected deduction of $450 from my salary this month without explanation. Please review this discrepancy.",
        db_path=db_path
    )
    results.append({"scenario": "2. Sensitive Payroll Deduction Dispute", "ticket_id": s2["ticket_id"], "status": s2["status"]})

    # Scenario 3: Harassment complaint (Sensitive HR-Confidential)
    s3 = create_ticket(
        employee_id="EMP-000008",
        subject="Harassment and hostile behavior complaint",
        description="I need to report severe ongoing harassment and hostile work environment issues involving my team lead in strict confidence.",
        db_path=db_path
    )
    results.append({"scenario": "3. Confidential Harassment Complaint", "ticket_id": s3["ticket_id"], "status": s3["status"]})

    # Scenario 4: Unavailable policy inquiry
    s4 = create_ticket(
        employee_id="EMP-000009",
        subject="Request for 6-month paid sabbatical for mountaineering expedition",
        description="I would like to apply for a 6-month fully paid sabbatical leave to attend an international high-altitude mountaineering trek.",
        db_path=db_path
    )
    results.append({"scenario": "4. Unavailable Policy Clarification", "ticket_id": s4["ticket_id"], "status": s4["status"]})

    # Scenario 5: Health insurance policy version retrieval
    s5 = create_ticket(
        employee_id="EMP-000010",
        subject="Health insurance enrollment window and guidelines",
        description="What is the official procedure and enrollment window for enrolling in the company health insurance plan?",
        db_path=db_path
    )
    results.append({"scenario": "5. Policy Version Selection", "ticket_id": s5["ticket_id"], "status": s5["status"]})

    # Scenario 6: Overdue SLA ticket (created in the past, sensitive so it remains In_Progress)
    past_date = "2026-10-14T09:00:00Z"
    s6 = create_ticket(
        employee_id="EMP-000011",
        subject="Disputed payroll tax deduction shortage pending from last month",
        description="My paycheck shortage dispute regarding unexpected tax deductions was submitted two weeks ago and is still pending specialist audit.",
        created_at=past_date,
        db_path=db_path
    )
    results.append({"scenario": "6. Overdue SLA Ticket", "ticket_id": s6["ticket_id"], "status": s6["status"]})

    return results

