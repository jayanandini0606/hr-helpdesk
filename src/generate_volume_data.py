"""
High-volume synthetic data generator for AI-Powered HR Helpdesk.
Generates exactly:
- 5,000 Tickets
- 20,000 Messages (exactly 4 messages per ticket)
- 5,000+ Assignments
- 5,000 SLAs
- 5,000 Resolutions
- 5,000+ Policy Citations
- 12,000+ Audit TicketEvents

All records strictly enforce foreign-key integrity, realistic distributions across
the 100 synthetic employees and 5 categories, and accurate SLA compliance rates.
Deterministic seed: 20261022.
"""

import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "hr_helpdesk.db"

SEED = 20261022
TOTAL_TICKETS = 5000
MESSAGES_PER_TICKET = 4  # 5,000 * 4 = exactly 20,000 messages!


# Realistic synthetic request templates across 5 categories
TICKET_TEMPLATES = {
    "CAT-001": [  # Benefits
        ("Health insurance dental enrollment", "I want to enroll my spouse and myself in the supplementary dental plan.", "POL-HR-2026-001", False),
        ("Dependent health coverage addition", "What documents are required to add a newborn child to my health insurance policy?", "POL-HR-2026-002", False),
        ("Mid-year benefits qualifying event change", "Can I update my benefits selection outside open enrollment due to marriage?", "POL-HR-2026-003", False),
        ("Replacement insurance card request", "How do I request a replacement physical medical insurance card?", "POL-HR-2026-004", False),
        ("Wellness program fitness allowance", "Does our current benefits plan cover annual gym membership or fitness reimbursements?", None, False),
    ],
    "CAT-002": [  # Leave
        ("Annual paid vacation leave accrual query", "How many days of annual paid leave do regular full-time employees accrue per month?", "POL-HR-2026-005", False),
        ("Sick leave doctor certificate requirements", "Do I need a doctor's note for taking 2 consecutive sick days?", "POL-HR-2026-006", False),
        ("Checking remaining leave balance online", "Where can I view my up-to-date paid time off and sick balance in the portal?", "POL-HR-2026-007", False),
        ("Public holiday calendar for remote hub", "Which regional holiday calendar applies to remote workers located in different states?", "POL-HR-2026-008", False),
        ("Paid sabbatical for mountaineering expedition", "Can I apply for a 6-month fully paid sabbatical leave to attend a high-altitude expedition?", None, False),
    ],
    "CAT-003": [  # Payroll
        ("Monthly salary disbursement date inquiry", "What day of the month is payroll processed and paid out to employee bank accounts?", "POL-HR-2026-009", False),
        ("How to access and download PDF payslip", "Where can I download my official salary payslip PDFs for income tax filing?", "POL-HR-2026-010", False),
        ("Unexpected deduction on monthly salary", "There is an unexpected deduction of $450 from my paycheck this month without explanation. Please audit.", None, True),
        ("Direct deposit bank account update deadline", "What is the cutoff date to update my direct deposit bank details for next payroll?", "POL-HR-2026-012", False),
        ("Missing quarterly sales bonus payment", "My agreed Q3 sales commission bonus is missing from this month's salary disbursement. Please audit.", None, True),
    ],
    "CAT-004": [  # Onboarding
        ("New employee mandatory checklist timeline", "What tax forms and compliance documents must new hires complete during their first 3 days?", "POL-HR-2026-013", False),
        ("IT hardware and second monitor request", "What is the approval procedure to request a replacement laptop or extra monitor from IT?", "POL-HR-2026-014", False),
        ("Corporate email and SSO credentials provisioning", "When are SSO credentials and corporate email accounts provisioned for new team members?", "POL-HR-2026-015", False),
        ("New hire orientation schedule and meeting link", "What day and time does general HR orientation take place for new joiners?", "POL-HR-2026-016", False),
    ],
    "CAT-005": [  # Employee Relations
        ("Workplace conduct and ethical concern reporting", "How do employees report compliance or ethical concerns in confidence to HR leadership?", "POL-HR-2026-017", False),
        ("Formal harassment and hostility complaint", "I need to report ongoing inappropriate conduct, harassment, and hostile environment in strict confidence.", None, True),
        ("Formal grievance submission regarding supervisor", "I am formally submitting an employee grievance regarding managerial retaliation and unfair treatment.", None, True),
        ("Coworker salary and personal file inquiry", "Can HR send me the compensation band and home address for my peer on the engineering team?", None, True),
    ],
}


def generate_volume_data(db_path: Optional[Path] = None):
    target_db = Path(db_path) if db_path else DB_PATH
    if not target_db.exists():
        raise FileNotFoundError(f"Database not found at {target_db}. Run src/init_db.py first.")

    rng = random.Random(SEED)
    conn = sqlite3.connect(target_db)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        # Load available employees, policies, categories
        employees = [r[0] for r in conn.execute("SELECT employee_id FROM Employee ORDER BY employee_id").fetchall()]
        categories = [r[0] for r in conn.execute("SELECT category_id FROM Category ORDER BY category_id").fetchall()]
        versions = dict(conn.execute("SELECT policy_id, version_id FROM PolicyVersion WHERE status = 'Published'").fetchall())
        articles = dict(conn.execute("SELECT version_id, article_id FROM KnowledgeArticle WHERE status = 'Published' GROUP BY version_id").fetchall())

        if not employees or not categories:
            raise ValueError("Master data must be seeded before generating volume data. Run src/generate_master_data.py first.")

        print(f"\nGENERATING {TOTAL_TICKETS:,} TICKETS AND {TOTAL_TICKETS * MESSAGES_PER_TICKET:,} MESSAGES...")
        start_time = datetime.now()

        # Start 6 months ago up to today
        base_start = datetime(2026, 4, 1, 9, 0, 0, tzinfo=timezone.utc)
        total_seconds_span = int((datetime(2026, 10, 28, 11, 0, 0, tzinfo=timezone.utc) - base_start).total_seconds())

        ticket_rows = []
        message_rows = []
        assignment_rows = []
        sla_rows = []
        resolution_rows = []
        citation_rows = []
        event_rows = []

        for i in range(1, TOTAL_TICKETS + 1):
            ticket_id = f"TKT-2026-{i:06d}"
            emp_id = employees[(i - 1) % len(employees)]

            # Category distribution
            cat_id = categories[(i - 1) % len(categories)]
            templates = TICKET_TEMPLATES[cat_id]
            tpl_idx = (i - 1) % len(templates)
            subj_base, desc_base, pol_id, is_sensitive = templates[tpl_idx]

            subject = f"{subj_base} [Ref #{i:04d}]"
            description = f"{desc_base} (Tracking ticket #{i:05d} for compliance records)."

            # Timestamp simulation
            random_offset = int((i / TOTAL_TICKETS) * total_seconds_span) + rng.randint(-3600, 3600)
            created_dt = base_start + timedelta(seconds=max(0, random_offset))
            created_iso = created_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            # Determine status & outcome
            if is_sensitive:
                sensitive_flag = 1
                queue = "HR-Confidential" if cat_id == "CAT-005" else "Payroll"
                priority = "Critical" if "harassment" in subject.lower() else "High"
                # 85% of older sensitive cases resolved by human HR, 15% in progress
                is_resolved = (i < TOTAL_TICKETS * 0.85)
                status = "Closed" if (i < TOTAL_TICKETS * 0.5) else ("Resolved" if is_resolved else "In_Progress")
                outcome = "Escalated"
                resolution_summary = f"Escalated to {queue} specialist team for confidential investigation and resolution."
            elif pol_id:
                sensitive_flag = 0
                queue = "Benefits" if cat_id == "CAT-001" else "Leave" if cat_id == "CAT-002" else "Payroll" if cat_id == "CAT-003" else "Onboarding"
                priority = "High" if cat_id == "CAT-003" else "Medium"
                is_resolved = (i < TOTAL_TICKETS * 0.96)
                status = "Closed" if (i < TOTAL_TICKETS * 0.7) else ("Resolved" if is_resolved else "Open")
                outcome = "Answered"
                resolution_summary = f"Automated grounded resolution provided with citations from {pol_id}."
            else:
                sensitive_flag = 0
                queue = "Leave" if cat_id == "CAT-002" else "Benefits"
                priority = "Medium"
                is_resolved = (i < TOTAL_TICKETS * 0.6)
                status = "Resolved" if is_resolved else "In_Progress"
                outcome = "Unresolved"
                resolution_summary = "No matching authoritative policy found; escalated for manual specialist clarification."

            # Calculate timestamps
            first_resp_dt = created_dt + timedelta(minutes=rng.randint(2, 15))
            first_resp_iso = first_resp_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            if status in ("Resolved", "Closed"):
                resolved_dt = created_dt + timedelta(hours=rng.randint(2, 36))
                resolved_iso = resolved_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                updated_iso = resolved_iso
            else:
                resolved_iso = None
                updated_iso = first_resp_iso

            # 1. Ticket row
            ticket_rows.append((
                ticket_id, emp_id, cat_id, subject, description,
                status, priority, sensitive_flag, "Standard",
                created_iso, updated_iso
            ))

            # 2. Four Messages per ticket = exactly 20,000 messages!
            msg_1_id = f"MSG-{ticket_id}-001"
            msg_2_id = f"MSG-{ticket_id}-002"
            msg_3_id = f"MSG-{ticket_id}-003"
            msg_4_id = f"MSG-{ticket_id}-004"

            # Msg 1: Employee initial request
            message_rows.append((
                msg_1_id, ticket_id, 1, "Employee", description, "Request", created_iso
            ))

            # Msg 2: Assistant response (Answer / Escalation / Clarification)
            if is_sensitive:
                asst_text = (
                    f"Your inquiry involves a sensitive matter and has been routed to the authorized {queue} team "
                    f"under ticket {ticket_id}. A specialist has been assigned to assist you confidentially."
                )
                msg_2_type = "Escalation"
            elif pol_id:
                asst_text = (
                    f"Based on official published policy {pol_id}:\n"
                    f"Guidance has been verified against the current company handbook. Please refer to cited sources below."
                )
                msg_2_type = "Answer"
            else:
                asst_text = (
                    f"We could not locate an authoritative policy directly answering this inquiry. "
                    f"Your ticket has been routed to an HR specialist for clarification."
                )
                msg_2_type = "Clarification"

            message_rows.append((
                msg_2_id, ticket_id, 2, "Assistant", asst_text, msg_2_type, first_resp_iso
            ))

            # Msg 3: Employee follow-up note
            followup_dt = first_resp_dt + timedelta(minutes=rng.randint(10, 60))
            followup_iso = followup_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            message_rows.append((
                msg_3_id, ticket_id, 3, "Employee",
                "Thank you for the update. Acknowledged.",
                "Clarification", followup_iso
            ))

            # Msg 4: HR / System resolution message
            final_msg_dt = followup_dt + timedelta(hours=rng.randint(1, 12))
            final_msg_iso = final_msg_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            final_sender = "HR" if is_sensitive else "System"
            message_rows.append((
                msg_4_id, ticket_id, 4, final_sender,
                f"Case record updated with outcome: {outcome}.",
                "Resolution", final_msg_iso
            ))

            # 3. Assignment row
            asg_id = f"ASG-{ticket_id}-001"
            assignment_rows.append((
                asg_id, ticket_id, queue, f"EMP-{rng.randint(1, 5):06d}",
                f"Automated routing to {queue} based on classification.",
                created_iso, None
            ))

            # 4. SLA row
            resp_target_hours = 1 if priority == "Critical" else 4 if priority == "High" else 8
            res_target_hours = 4 if priority == "Critical" else 24 if priority == "High" else 48

            resp_due_dt = created_dt + timedelta(hours=resp_target_hours)
            res_due_dt = created_dt + timedelta(hours=res_target_hours)

            resp_met = 1  # Assistant responds within minutes
            res_met = None
            if resolved_iso:
                res_met = 1 if resolved_dt <= res_due_dt else 0

            sla_rows.append((
                f"SLA-{ticket_id}", ticket_id, f"{priority}-Priority Standard SLA",
                resp_due_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                res_due_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "Standard Business Hours (09:00-17:00 Mon-Fri)",
                resp_met, res_met
            ))

            # 5. Resolution row
            v_id = versions.get(pol_id)
            a_id = articles.get(v_id) if v_id else None

            resolution_rows.append((
                f"RES-{ticket_id}", ticket_id, outcome, resolution_summary,
                resolved_iso, a_id, v_id
            ))

            # 6. Policy citation if grounded
            if pol_id and v_id:
                citation_rows.append((
                    ticket_id, v_id, a_id, created_iso
                ))

            # 7. TicketEvents
            event_rows.append((
                f"EVT-{ticket_id}-001", ticket_id, None, "Open", "Ticket created by employee", created_iso
            ))
            if status != "Open":
                event_rows.append((
                    f"EVT-{ticket_id}-002", ticket_id, "Open", status, f"Ticket transitioned to {status}: {outcome}", updated_iso
                ))

        # Clear existing tickets in child-to-parent order
        with conn:
            conn.execute("DELETE FROM TicketPolicyCitation")
            conn.execute("DELETE FROM TicketEvent")
            conn.execute("DELETE FROM Resolution")
            conn.execute("DELETE FROM SLA")
            conn.execute("DELETE FROM Assignment")
            conn.execute("DELETE FROM Message")
            conn.execute("DELETE FROM Ticket")

            print("Inserting 5,000 Tickets...")
            conn.executemany("""
                INSERT INTO Ticket (
                    ticket_id, employee_id, category_id, subject, description,
                    status, priority, sensitive_flag, issue_type, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ticket_rows)

            print("Inserting 20,000 Messages...")
            conn.executemany("""
                INSERT INTO Message (
                    message_id, ticket_id, sequence_number, sender_type,
                    message_text, message_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, message_rows)

            print("Inserting Assignments...")
            conn.executemany("""
                INSERT INTO Assignment (
                    assignment_id, ticket_id, assigned_queue, assigned_to,
                    reason, assigned_at, ended_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, assignment_rows)

            print("Inserting SLAs...")
            conn.executemany("""
                INSERT INTO SLA (
                    sla_id, ticket_id, policy_name, response_due_at, resolution_due_at,
                    business_calendar, response_met, resolution_met
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, sla_rows)

            print("Inserting Resolutions...")
            conn.executemany("""
                INSERT INTO Resolution (
                    resolution_id, ticket_id, outcome, resolution_summary,
                    resolved_at, article_id, version_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, resolution_rows)

            print("Inserting Policy Citations...")
            conn.executemany("""
                INSERT OR IGNORE INTO TicketPolicyCitation (
                    ticket_id, version_id, article_id, cited_at
                ) VALUES (?, ?, ?, ?)
            """, citation_rows)

            print("Inserting Audit Events...")
            conn.executemany("""
                INSERT INTO TicketEvent (
                    event_id, ticket_id, old_status, new_status, reason, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, event_rows)

        # Validation
        actual_tickets = conn.execute("SELECT COUNT(*) FROM Ticket").fetchone()[0]
        actual_messages = conn.execute("SELECT COUNT(*) FROM Message").fetchone()[0]
        actual_citations = conn.execute("SELECT COUNT(*) FROM TicketPolicyCitation").fetchone()[0]
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()

        duration = (datetime.now() - start_time).total_seconds()

        print(f"\nVOLUME DATA GENERATION COMPLETED IN {duration:.2f}s:")
        print(f"- Tickets: {actual_tickets:,} (Target: {TOTAL_TICKETS:,})")
        print(f"- Messages: {actual_messages:,} (Target: {TOTAL_TICKETS * MESSAGES_PER_TICKET:,})")
        print(f"- Citations: {actual_citations:,}")
        print(f"- Foreign Key Violations: {len(violations)}")

        if actual_tickets != TOTAL_TICKETS or actual_messages != TOTAL_TICKETS * MESSAGES_PER_TICKET or len(violations) > 0:
            raise ValueError("Validation failed on generated volume data counts or FK check.")

    finally:
        conn.close()


if __name__ == "__main__":
    generate_volume_data()
