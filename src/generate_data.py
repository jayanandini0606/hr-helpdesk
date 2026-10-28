"""
Unified, parameterized synthetic data generator for AI-Powered HR Helpdesk.
Implements the complete generation pipeline:
1. Master Tables: Department (5), Employee (100), Category (5), PolicyDocument (20), PolicyVersion (40), KnowledgeArticle (150).
2. Transaction Tables: Tickets (5,000), Messages (20,000), Assignments, SLAs, Resolutions, Citations, Events.
3. Labelled Anomaly Injection:
   - obsolete_policy_citation: Answer cites a Retired policy version.
   - sensitive_misrouted: Sensitive harassment/grievance sent to general queue.
   - sla_calendar_anomaly: SLA calculated ignoring business calendar.
   - unsupported_policy_hallucination: Unsupported policy question answered as fact.
4. Separate Ground Truth Export: evaluation/ground_truth.json and evaluation/ground_truth.csv.
5. CSV Data Export: data/export/*.csv.

Deterministic seed: 20261022.
"""

import argparse
import csv
import json
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "hr_helpdesk.db"
EXPORT_DIR = PROJECT_ROOT / "data" / "export"
GROUND_TRUTH_JSON = PROJECT_ROOT / "evaluation" / "ground_truth.json"
GROUND_TRUTH_CSV = PROJECT_ROOT / "evaluation" / "ground_truth.csv"

SEED = 20261022

# --------------------------------------------------
# Master Data Definitions
# --------------------------------------------------

DEPARTMENTS = [
    ("DPT-001", "Human Resources", "HR-General"),
    ("DPT-002", "Information Technology", "IT-Support"),
    ("DPT-003", "Finance", "Payroll"),
    ("DPT-004", "Engineering", "Engineering-Operations"),
    ("DPT-005", "Operations", "Operations"),
]

CATEGORIES = [
    ("CAT-001", "Benefits", "Benefits", "Medium"),
    ("CAT-002", "Leave", "Leave", "Medium"),
    ("CAT-003", "Payroll", "Payroll", "High"),
    ("CAT-004", "Onboarding", "Onboarding", "Medium"),
    ("CAT-005", "Employee Relations", "HR-Confidential", "High"),
]

CATEGORY_ID_BY_NAME = {c[1]: c[0] for c in CATEGORIES}

POLICY_TEMPLATES = [
    # Benefits (4 policies)
    ("Benefits", "Health Insurance Enrollment",
     "Employees must review the published annual enrollment window. Eligibility depends on active employment status and the selected benefits tier. Routine queries are answered directly; individual plan changes require submitting the benefits enrollment form to the Benefits team.",
     "All"),
    ("Benefits", "Dependent Coverage",
     "Dependent coverage requests require supporting documentation such as marriage or birth certificates within 30 days of a qualifying life event. HR Benefits verifies all certificates before enrolling dependents.",
     "Employee"),
    ("Benefits", "Benefits Enrollment Changes",
     "Mid-year benefits changes are permitted only following a verified qualifying life event (e.g. marriage, birth, or spouse coverage change). Documentation must be submitted within 30 days.",
     "Employee"),
    ("Benefits", "Insurance Card Requests",
     "Employees can download digital insurance cards directly from the insurer portal. Physical replacement cards may be requested through the Benefits portal and arrive within 7 to 10 business days.",
     "Employee"),

    # Leave (4 policies)
    ("Leave", "Annual Leave Policy",
     "Full-time regular employees accrue 1.5 days of annual paid leave per month (up to 18 days annually). Leave requests must be submitted through the leave management portal at least 5 business days in advance and approved by the direct manager.",
     "All"),
    ("Leave", "Sick Leave Procedure",
     "Employees are entitled to 10 days of paid sick leave per calendar year. Notification to the immediate manager is required by 09:00 AM on the day of absence. Medical certification is required for sick leave exceeding 3 consecutive business days.",
     "Employee"),
    ("Leave", "Leave Balance Enquiries",
     "Current leave balances can be viewed anytime on the HR Employee Self-Service portal under 'Time & Absence'. The Helpdesk does not manually compute or modify balances without manager and HR approval.",
     "Employee"),
    ("Leave", "Holiday Calendar",
     "Official public holidays are observed based on the primary work location indicated in the employee profile. Remote employees follow the statutory holidays of their contractual regional hub.",
     "All"),

    # Payroll (4 policies)
    ("Payroll", "Payroll Schedule",
     "Salaries are disbursed on the final business day of each calendar month. If the final day falls on a weekend or public holiday, disbursement occurs on the preceding business day.",
     "All"),
    ("Payroll", "Payslip Access",
     "Digital payslips are generated and accessible via the secure Payroll Self-Service portal 2 days prior to salary disbursement. Employees require active multi-factor authentication (MFA) to access payslip PDFs.",
     "Employee"),
    ("Payroll", "Payroll Discrepancies",
     "Reported salary discrepancies, deduction queries, or missing reimbursements require review by the Payroll team. The Helpdesk must never post employee compensation numbers or banking details in general queues.",
     "HR"),
    ("Payroll", "Bank Account Changes",
     "Bank account updates for salary deposit must be submitted via the secure Payroll Portal before the 15th day of the month. Never share full account numbers or OTPs through helpdesk tickets.",
     "Employee"),

    # Onboarding (4 policies)
    ("Onboarding", "New Employee Checklist",
     "New hires must complete statutory tax declarations, emergency contact submissions, and policy acknowledgement forms within their first 3 business days of employment.",
     "Employee"),
    ("Onboarding", "Equipment Requests",
     "Standard hardware (laptop, monitor, peripherals) is issued during the first week. Replacement or upgrade requests require direct manager pre-approval and are fulfilled by IT-Support.",
     "Employee"),
    ("Onboarding", "Account Provisioning",
     "Corporate email, SSO credentials, and tool permissions are provisioned automatically 48 hours prior to the official start date upon HR Onboarding clearance. Passwords are never sent in plain text.",
     "Employee"),
    ("Onboarding", "Orientation Scheduling",
     "General HR orientation sessions take place every Monday at 10:00 AM. Schedule invites and meeting links are distributed to new hires and their managers by the Onboarding team via calendar invite.",
     "Employee"),

    # Employee Relations (4 policies)
    ("Employee Relations", "Workplace Concern Reporting",
     "Employees may report ethical violations, safety concerns, or workplace conflicts to HR. Reports are handled with strict confidentiality and routed exclusively to designated HR-Confidential partners.",
     "HR"),
    ("Employee Relations", "Harassment Complaint Handling",
     "The company maintains a zero-tolerance policy for harassment, discrimination, or retaliation. All formal complaints trigger an immediate confidential review by authorized Employee Relations personnel. AI systems must never attempt automated resolution.",
     "HR"),
    ("Employee Relations", "Grievance Escalation",
     "Formal workplace grievances must be submitted in writing detailing dates, parties involved, and specific incidents. Grievances are routed directly to Senior HR Leadership and logged under HR-Confidential.",
     "HR"),
    ("Employee Relations", "Confidential Case Access",
     "Confidential employee relations case files, investigation notes, and disciplinary records are strictly restricted to authorized HR Partners and Legal counsel. Unauthorized access or disclosure constitutes a gross policy violation.",
     "HR"),
]

FIRST_NAMES = [
    "Aarav", "Aditi", "Ananya", "Arjun", "Diya",
    "Ishaan", "Kavya", "Meera", "Neha", "Rahul",
    "Riya", "Sanjay", "Sneha", "Varun", "Vikram",
    "Priya", "Kiran", "Nikhil", "Pooja", "Rohan",
]

LAST_NAMES = [
    "Sharma", "Reddy", "Rao", "Patel", "Kumar",
    "Verma", "Singh", "Iyer", "Gupta", "Nair",
    "Das", "Joshi", "Mehta", "Roy", "Kapoor",
]

# Standard request templates
TICKET_TEMPLATES = {
    "CAT-001": [
        ("Health insurance dental enrollment", "I want to enroll my spouse and myself in the supplementary dental plan.", "POL-HR-2026-001", False),
        ("Dependent health coverage addition", "What documents are required to add a newborn child to my health insurance policy?", "POL-HR-2026-002", False),
        ("Mid-year benefits qualifying event change", "Can I update my benefits selection outside open enrollment due to marriage?", "POL-HR-2026-003", False),
        ("Replacement insurance card request", "How do I request a replacement physical medical insurance card?", "POL-HR-2026-004", False),
        ("Wellness program fitness allowance", "Does our current benefits plan cover annual gym membership or fitness reimbursements?", None, False),
    ],
    "CAT-002": [
        ("Annual paid vacation leave accrual query", "How many days of annual paid leave do regular full-time employees accrue per month?", "POL-HR-2026-005", False),
        ("Sick leave doctor certificate requirements", "Do I need a doctor's note for taking 2 consecutive sick days?", "POL-HR-2026-006", False),
        ("Checking remaining leave balance online", "Where can I view my up-to-date paid time off and sick balance in the portal?", "POL-HR-2026-007", False),
        ("Public holiday calendar for remote hub", "Which regional holiday calendar applies to remote workers located in different states?", "POL-HR-2026-008", False),
        ("Paid sabbatical for mountaineering expedition", "Can I apply for a 6-month fully paid sabbatical leave to attend a high-altitude expedition?", None, False),
    ],
    "CAT-003": [
        ("Monthly salary disbursement date inquiry", "What day of the month is payroll processed and paid out to employee bank accounts?", "POL-HR-2026-009", False),
        ("How to access and download PDF payslip", "Where can I download my official salary payslip PDFs for income tax filing?", "POL-HR-2026-010", False),
        ("Unexpected deduction on monthly salary", "There is an unexpected deduction of $450 from my paycheck this month without explanation. Please audit.", None, True),
        ("Direct deposit bank account update deadline", "What is the cutoff date to update my direct deposit bank details for next payroll?", "POL-HR-2026-012", False),
        ("Missing quarterly sales bonus payment", "My agreed Q3 sales commission bonus is missing from this month's salary disbursement. Please audit.", None, True),
    ],
    "CAT-004": [
        ("New employee mandatory checklist timeline", "What tax forms and compliance documents must new hires complete during their first 3 days?", "POL-HR-2026-013", False),
        ("IT hardware and second monitor request", "What is the approval procedure to request a replacement laptop or extra monitor from IT?", "POL-HR-2026-014", False),
        ("Corporate email and SSO credentials provisioning", "When are SSO credentials and corporate email accounts provisioned for new team members?", "POL-HR-2026-015", False),
        ("New hire orientation schedule and meeting link", "What day and time does general HR orientation take place for new joiners?", "POL-HR-2026-016", False),
    ],
    "CAT-005": [
        ("Workplace conduct and ethical concern reporting", "How do employees report compliance or ethical concerns in confidence to HR leadership?", "POL-HR-2026-017", False),
        ("Formal harassment and hostility complaint", "I need to report ongoing inappropriate conduct, harassment, and hostile environment in strict confidence.", None, True),
        ("Formal grievance submission regarding supervisor", "I am formally submitting an employee grievance regarding managerial retaliation and unfair treatment.", None, True),
        ("Coworker salary and personal file inquiry", "Can HR send me the compensation band and home address for my peer on the engineering team?", None, True),
    ],
}


def clear_all_tables(conn: sqlite3.Connection):
    """Safely clear child tables first to respect foreign-key constraints."""
    tables = [
        "TicketPolicyCitation", "TicketEvent", "Resolution", "SLA",
        "Assignment", "Message", "Ticket", "KnowledgeArticle",
        "PolicyVersion", "PolicyDocument", "Employee", "Category", "Department"
    ]
    for t in tables:
        conn.execute(f"DELETE FROM {t}")


def generate_dataset(
    target_tickets: int = 5000,
    db_path: Optional[Path] = None,
    seed: int = SEED,
    export_csv: bool = True
) -> Dict[str, Any]:
    """Generates the master and transactional tables with exact scale and injected anomalies."""
    target_db = Path(db_path) if db_path else DB_PATH
    rng = random.Random(seed)

    conn = sqlite3.connect(target_db)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        with conn:
            clear_all_tables(conn)

            # --------------------------------------------------
            # 1. Master: Department & Category
            # --------------------------------------------------
            conn.executemany("INSERT INTO Department VALUES (?, ?, ?)", DEPARTMENTS)
            conn.executemany("INSERT INTO Category VALUES (?, ?, ?, ?)", CATEGORIES)

            # --------------------------------------------------
            # 2. Master: Employee (100)
            # --------------------------------------------------
            dept_ids = [d[0] for d in DEPARTMENTS]
            employee_rows = []
            for i in range(1, 101):
                emp_id = f"EMP-{i:06d}"
                first = FIRST_NAMES[(i - 1) % len(FIRST_NAMES)]
                last = LAST_NAMES[((i - 1) // len(FIRST_NAMES)) % len(LAST_NAMES)]
                full_name = f"{first} {last} {i:03d}"
                dept_id = dept_ids[(i - 1) % len(dept_ids)]
                manager_id = None if i <= 5 else f"EMP-{((i - 6) % 5) + 1:06d}"
                audience = "Manager" if i <= 5 else "Employee"
                status = "Onboarding" if i % 17 == 0 else "Inactive" if i % 23 == 0 else "Active"
                employee_rows.append((
                    emp_id, full_name, dept_id, manager_id, status, audience, "2026-01-01T09:00:00Z"
                ))
            conn.executemany("INSERT INTO Employee VALUES (?, ?, ?, ?, ?, ?, ?)", employee_rows)

            # --------------------------------------------------
            # 3. Master: PolicyDocument (20) & PolicyVersion (40)
            # --------------------------------------------------
            policy_rows = []
            version_rows = []
            for i, (category, title, text, audience) in enumerate(POLICY_TEMPLATES, start=1):
                policy_id = f"POL-HR-2026-{i:03d}"
                cat_id = CATEGORY_ID_BY_NAME[category]
                owner_dept_id = "DPT-003" if category == "Payroll" else ("DPT-002" if title == "Account Provisioning" else "DPT-001")

                policy_rows.append((policy_id, title, cat_id, owner_dept_id, audience, "2026-01-01T09:00:00Z"))

                if i <= 18:
                    version_rows.append((f"VER-{policy_id}-01", policy_id, 1, "2026-01-01", "2026-03-31", f"[Historical Q1 Policy] {text}", "Retired", "2026-01-01T09:00:00Z"))
                    version_rows.append((f"VER-{policy_id}-02", policy_id, 2, "2026-04-01", None, f"[Current Active Policy] {text}", "Published", "2026-04-01T09:00:00Z"))
                else:
                    version_rows.append((f"VER-{policy_id}-01", policy_id, 1, "2026-01-01", None, f"[Current Active Policy] {text}", "Published", "2026-01-01T09:00:00Z"))
                    version_rows.append((f"VER-{policy_id}-02", policy_id, 2, "2027-01-01", None, f"[Upcoming Draft Revision] {text}", "Draft", "2026-10-01T09:00:00Z"))

            conn.executemany("INSERT INTO PolicyDocument VALUES (?, ?, ?, ?, ?, ?)", policy_rows)
            conn.executemany("INSERT INTO PolicyVersion VALUES (?, ?, ?, ?, ?, ?, ?, ?)", version_rows)

            # --------------------------------------------------
            # 4. Master: KnowledgeArticle (150)
            # --------------------------------------------------
            article_rows = []
            for i in range(1, 151):
                tpl_idx = (i - 1) % len(POLICY_TEMPLATES)
                category, title, text, _ = POLICY_TEMPLATES[tpl_idx]
                policy_num = tpl_idx + 1
                pol_id = f"POL-HR-2026-{policy_num:03d}"
                v_id = f"VER-{pol_id}-02" if policy_num <= 18 else f"VER-{pol_id}-01"
                cat_id = CATEGORY_ID_BY_NAME[category]

                article_rows.append((
                    f"KB-{i:06d}", f"{title} — Guidance Note #{i:03d}",
                    f"Summary: {text[:120]}... Refer to official policy for comprehensive procedures.",
                    cat_id, v_id, "Published", "2026-04-01T09:00:00Z"
                ))
            conn.executemany("INSERT INTO KnowledgeArticle VALUES (?, ?, ?, ?, ?, ?, ?)", article_rows)

            # --------------------------------------------------
            # 5. Dependent Transactions: Tickets & Messages
            # --------------------------------------------------
            emp_ids = [e[0] for e in employee_rows]
            cat_ids = [c[0] for c in CATEGORIES]
            published_versions = {f"POL-HR-2026-{i:03d}": (f"VER-POL-HR-2026-{i:03d}-02" if i <= 18 else f"VER-POL-HR-2026-{i:03d}-01") for i in range(1, 21)}
            retired_versions = {f"POL-HR-2026-{i:03d}": f"VER-POL-HR-2026-{i:03d}-01" for i in range(1, 19)}

            articles_by_version = {}
            for art in article_rows:
                v_id = art[4]
                if v_id not in articles_by_version:
                    articles_by_version[v_id] = art[0]

            base_start = datetime(2026, 4, 1, 9, 0, 0, tzinfo=timezone.utc)
            total_span_sec = int((datetime(2026, 10, 28, 11, 0, 0, tzinfo=timezone.utc) - base_start).total_seconds())

            ticket_rows = []
            message_rows = []
            assignment_rows = []
            sla_rows = []
            resolution_rows = []
            citation_rows = []
            event_rows = []
            ground_truth_records = []

            # Specific indices for deliberate anomaly injection (if full scale, e.g. at fixed positions)
            anomaly_map = {}
            if target_tickets >= 100:
                anomaly_map[101] = "obsolete_policy_citation"
                anomaly_map[102] = "sensitive_misrouted"
                anomaly_map[103] = "sla_calendar_anomaly"
                anomaly_map[104] = "unsupported_policy_hallucination"

            for i in range(1, target_tickets + 1):
                ticket_id = f"TKT-2026-{i:06d}"
                emp_id = emp_ids[(i - 1) % len(emp_ids)]
                cat_id = cat_ids[(i - 1) % len(cat_ids)]
                templates = TICKET_TEMPLATES[cat_id]
                tpl = templates[(i - 1) % len(templates)]
                subj_base, desc_base, pol_id, is_sensitive = tpl

                subject = f"{subj_base} [Ref #{i:04d}]"
                description = f"{desc_base} (Ref #{i:05d})."

                offset_sec = int((i / target_tickets) * total_span_sec) + rng.randint(-3600, 3600)
                created_dt = base_start + timedelta(seconds=max(0, offset_sec))
                created_iso = created_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

                issue_type = anomaly_map.get(i, "Standard")

                # Baseline logic
                if is_sensitive:
                    sensitive_flag = 1
                    assigned_queue = "HR-Confidential" if cat_id == "CAT-005" else "Payroll"
                    priority = "Critical" if "harassment" in subject.lower() else "High"
                    is_resolved = (i < target_tickets * 0.85)
                    status = "Closed" if (i < target_tickets * 0.5) else ("Resolved" if is_resolved else "In_Progress")
                    outcome = "Escalated"
                    resolution_summary = f"Escalated to {assigned_queue} specialist team for confidential investigation and resolution."
                elif pol_id:
                    sensitive_flag = 0
                    assigned_queue = "Benefits" if cat_id == "CAT-001" else "Leave" if cat_id == "CAT-002" else "Payroll" if cat_id == "CAT-003" else "Onboarding"
                    priority = "High" if cat_id == "CAT-003" else "Medium"
                    is_resolved = (i < target_tickets * 0.96)
                    status = "Closed" if (i < target_tickets * 0.7) else ("Resolved" if is_resolved else "Open")
                    outcome = "Answered"
                    resolution_summary = f"Automated grounded resolution provided with citations from {pol_id}."
                else:
                    sensitive_flag = 0
                    assigned_queue = "Leave" if cat_id == "CAT-002" else "Benefits"
                    priority = "Medium"
                    is_resolved = (i < target_tickets * 0.6)
                    status = "Resolved" if is_resolved else "In_Progress"
                    outcome = "Unresolved"
                    resolution_summary = "No matching authoritative policy found; escalated for manual specialist clarification."

                # Injected Deliberate Anomaly Overrides
                if issue_type == "obsolete_policy_citation":
                    # Anomaly 1: Answer cites Retired version 1 instead of active version 2
                    pol_id = "POL-HR-2026-001"
                    cited_version = retired_versions[pol_id]  # VER-POL-HR-2026-001-01 (Retired!)
                    gt_reason = "Answer generated citing a Retired policy version (VER-POL-HR-2026-001-01) rather than the active published version."
                elif issue_type == "sensitive_misrouted":
                    # Anomaly 2: Sensitive case sent to general queue HR-General
                    sensitive_flag = 1
                    assigned_queue = "HR-General"  # Misrouted!
                    gt_reason = "Confidential harassment complaint misrouted to general queue (HR-General) instead of HR-Confidential."
                elif issue_type == "sla_calendar_anomaly":
                    # Anomaly 3: SLA calculated ignoring business working calendar
                    gt_reason = "SLA deadline calculated without skipping weekend business hours."
                elif issue_type == "unsupported_policy_hallucination":
                    # Anomaly 4: Unsupported topic answered as fact
                    outcome = "Answered"  # Hallucinated answer!
                    resolution_summary = "Fabricated rule: 6-month mountaineering sabbatical is approved without manager consent."
                    gt_reason = "Unsupported policy request (paid mountaineering sabbatical) was hallucinated and answered as fact."

                # Timestamps
                first_resp_dt = created_dt + timedelta(minutes=rng.randint(2, 15))
                first_resp_iso = first_resp_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

                if status in ("Resolved", "Closed"):
                    resolved_dt = created_dt + timedelta(hours=rng.randint(2, 36))
                    resolved_iso = resolved_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    updated_iso = resolved_iso
                else:
                    resolved_iso = None
                    updated_iso = first_resp_iso

                ticket_rows.append((
                    ticket_id, emp_id, cat_id, subject, description,
                    status, priority, sensitive_flag, issue_type,
                    created_iso, updated_iso
                ))

                # Messages (exactly 4 per ticket)
                m1_id = f"MSG-{ticket_id}-001"
                m2_id = f"MSG-{ticket_id}-002"
                m3_id = f"MSG-{ticket_id}-003"
                m4_id = f"MSG-{ticket_id}-004"

                # Message 1: Request
                message_rows.append((m1_id, ticket_id, 1, "Employee", description, "Request", created_iso))

                # Message 2: Assistant
                if issue_type == "obsolete_policy_citation":
                    asst_msg = f"Based on historical policy {pol_id} (Version 1): Guidance from retired provisions."
                    msg_type = "Answer"
                elif is_sensitive and issue_type != "sensitive_misrouted":
                    asst_msg = f"Your request involves confidential HR handling and has been routed to {assigned_queue} under reference {ticket_id}."
                    msg_type = "Escalation"
                elif pol_id:
                    asst_msg = f"Based on official published policy {pol_id}: Guidance has been verified against current regulations."
                    msg_type = "Answer"
                else:
                    asst_msg = "We could not locate an authoritative policy directly answering this inquiry. Routed for manual clarification."
                    msg_type = "Clarification"

                message_rows.append((m2_id, ticket_id, 2, "Assistant", asst_msg, msg_type, first_resp_iso))

                # Message 3: Employee follow-up
                m3_dt = first_resp_dt + timedelta(minutes=rng.randint(5, 45))
                m3_iso = m3_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                message_rows.append((m3_id, ticket_id, 3, "Employee", "Acknowledged. Thank you for the assistance.", "Clarification", m3_iso))

                # Message 4: Resolution / System finalization
                m4_dt = m3_dt + timedelta(hours=rng.randint(1, 8))
                m4_iso = m4_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                m4_sender = "HR" if is_sensitive else "System"
                message_rows.append((m4_id, ticket_id, 4, m4_sender, f"Case updated with outcome: {outcome}.", "Resolution", m4_iso))

                # Assignment
                assignment_rows.append((
                    f"ASG-{ticket_id}-001", ticket_id, assigned_queue, f"EMP-{rng.randint(1, 5):06d}",
                    f"Routing to {assigned_queue} based on classification.",
                    created_iso, None
                ))

                # SLA
                resp_hrs = 1 if priority == "Critical" else 4 if priority == "High" else 8
                res_hrs = 4 if priority == "Critical" else 24 if priority == "High" else 48

                resp_due_dt = created_dt + timedelta(hours=resp_hrs)
                if issue_type == "sla_calendar_anomaly":
                    # Bug: calculated with continuous 24/7 calendar without skipping weekend business hours
                    res_due_dt = created_dt + timedelta(hours=res_hrs)
                    calendar_name = "Calendar 24x7 (Excluded Required Business Hours)"
                else:
                    res_due_dt = created_dt + timedelta(hours=res_hrs + 48)  # standard business hours including weekend buffer
                    calendar_name = "Standard Business Hours (09:00-17:00 Mon-Fri)"

                res_met = 1 if (resolved_iso and resolved_dt <= res_due_dt) else (0 if resolved_iso else None)
                sla_rows.append((
                    f"SLA-{ticket_id}", ticket_id, f"{priority}-Priority Standard SLA",
                    resp_due_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    res_due_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    calendar_name, 1, res_met
                ))

                # Resolution
                target_vid = cited_version if issue_type == "obsolete_policy_citation" else (published_versions.get(pol_id) if pol_id else None)
                target_aid = articles_by_version.get(target_vid) if target_vid else None

                resolution_rows.append((
                    f"RES-{ticket_id}", ticket_id, outcome, resolution_summary,
                    resolved_iso, target_aid, target_vid
                ))

                # Citations
                if target_vid:
                    citation_rows.append((ticket_id, target_vid, target_aid, created_iso))

                # Events
                event_rows.append((f"EVT-{ticket_id}-001", ticket_id, None, "Open", "Ticket created by employee", created_iso))
                if status != "Open":
                    event_rows.append((f"EVT-{ticket_id}-002", ticket_id, "Open", status, f"Transitioned to {status}: {outcome}", updated_iso))

                # Ground Truth logging
                if issue_type != "Standard":
                    ground_truth_records.append({
                        "ticket_id": ticket_id,
                        "subject": subject,
                        "anomaly_category": issue_type,
                        "expected_behavior": "Should flag/reject during QA or evaluation",
                        "injected_fault_description": gt_reason,
                        "created_at": created_iso
                    })

            # Bulk insert
            conn.executemany("INSERT INTO Ticket VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ticket_rows)
            conn.executemany("INSERT INTO Message VALUES (?, ?, ?, ?, ?, ?, ?)", message_rows)
            conn.executemany("INSERT INTO Assignment VALUES (?, ?, ?, ?, ?, ?, ?)", assignment_rows)
            conn.executemany("INSERT INTO SLA VALUES (?, ?, ?, ?, ?, ?, ?, ?)", sla_rows)
            conn.executemany("INSERT INTO Resolution VALUES (?, ?, ?, ?, ?, ?, ?)", resolution_rows)
            conn.executemany("INSERT OR IGNORE INTO TicketPolicyCitation VALUES (?, ?, ?, ?)", citation_rows)
            conn.executemany("INSERT INTO TicketEvent VALUES (?, ?, ?, ?, ?, ?)", event_rows)

        # --------------------------------------------------
        # 6. Separate Ground Truth Export
        # --------------------------------------------------
        GROUND_TRUTH_JSON.parent.mkdir(parents=True, exist_ok=True)
        with open(GROUND_TRUTH_JSON, "w", encoding="utf-8") as f:
            json.dump({"total_anomalies": len(ground_truth_records), "records": ground_truth_records}, f, indent=2)

        if ground_truth_records:
            with open(GROUND_TRUTH_CSV, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(ground_truth_records[0].keys()))
                writer.writeheader()
                writer.writerows(ground_truth_records)

        # --------------------------------------------------
        # 7. CSV Seed Data Export
        # --------------------------------------------------
        if export_csv:
            EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            tables = [
                "Department", "Employee", "Category", "PolicyDocument", "PolicyVersion",
                "KnowledgeArticle", "Ticket", "Message", "Assignment", "SLA",
                "Resolution", "TicketPolicyCitation", "TicketEvent"
            ]
            for t in tables:
                cursor = conn.execute(f"SELECT * FROM {t}")
                col_names = [d[0] for d in cursor.description]
                rows = cursor.fetchall()
                csv_path = EXPORT_DIR / f"{t}.csv"
                with open(csv_path, "w", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(col_names)
                    writer.writerows(rows)

        # Summary checks
        total_tickets_actual = conn.execute("SELECT COUNT(*) FROM Ticket").fetchone()[0]
        total_messages_actual = conn.execute("SELECT COUNT(*) FROM Message").fetchone()[0]
        fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()

        return {
            "tickets": total_tickets_actual,
            "messages": total_messages_actual,
            "anomalies": len(ground_truth_records),
            "fk_violations": len(fk_violations),
            "seed": seed
        }

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic HR Helpdesk data")
    parser.add_argument("--scale", choices=["full", "starter"], default="full", help="Full (5000 tickets) or starter (25 tickets)")
    parser.add_argument("--tickets", type=int, help="Custom ticket count")
    parser.add_argument("--seed", type=int, default=SEED, help="Deterministic random seed")
    args = parser.parse_args()

    count = args.tickets if args.tickets else (5000 if args.scale == "full" else 25)
    res = generate_dataset(target_tickets=count, seed=args.seed)
    print(f"\nCompleted! Generated {res['tickets']:,} tickets, {res['messages']:,} messages, {res['anomalies']} anomalies. FK violations: {res['fk_violations']}")
