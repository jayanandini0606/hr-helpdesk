"""
Master data generation for the AI-Powered HR Helpdesk.
Generates deterministic synthetic demo data for:
- 5 Departments
- 100 Employees (first 5 managers, deterministic distribution)
- 5 Categories (Benefits, Leave, Payroll, Onboarding, Employee Relations)
- 20 Policy Documents
- 40 Policy Versions (2 per policy, covering Published, Retired, Draft)
- 150 Knowledge Articles (all linked to valid, published policy versions)

Deterministic seed: 20261022.
Enforces foreign key checks and transaction rollback on failure.
"""

import sqlite3
from pathlib import Path

# --------------------------------------------------
# Configuration
# --------------------------------------------------

SEED = 20261022
EMPLOYEE_COUNT = 100
POLICY_COUNT = 20
ARTICLE_COUNT = 150

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "hr_helpdesk.db"

# --------------------------------------------------
# 1. Department master data
# --------------------------------------------------

DEPARTMENTS = [
    ("DPT-001", "Human Resources", "HR-General"),
    ("DPT-002", "Information Technology", "IT-Support"),
    ("DPT-003", "Finance", "Payroll"),
    ("DPT-004", "Engineering", "Engineering-Operations"),
    ("DPT-005", "Operations", "Operations"),
]

# --------------------------------------------------
# 2. HR categories
# --------------------------------------------------

CATEGORIES = [
    ("CAT-001", "Benefits", "Benefits", "Medium"),
    ("CAT-002", "Leave", "Leave", "Medium"),
    ("CAT-003", "Payroll", "Payroll", "High"),
    ("CAT-004", "Onboarding", "Onboarding", "Medium"),
    ("CAT-005", "Employee Relations", "HR-Confidential", "High"),
]

CATEGORY_ID_BY_NAME = {
    name: category_id
    for category_id, name, _, _ in CATEGORIES
}

# --------------------------------------------------
# 3. Synthetic policy templates (20 policies across 5 categories)
# --------------------------------------------------

POLICY_TEMPLATES = [
    # Benefits (4 policies)
    ("Benefits", "Health Insurance Enrollment",
     "Employees must review the published annual enrollment window. Eligibility depends on active employment status and the selected benefits tier. Routine enrollment queries are answered directly, but individual plan changes require submitting the benefits enrollment form to the Benefits team.",
     "All"),
    ("Benefits", "Dependent Coverage",
     "Dependent coverage requests require supporting documentation such as marriage or birth certificates within 30 days of a qualifying life event. HR Benefits verifies all certificates before enrolling dependents.",
     "Employee"),
    ("Benefits", "Benefits Enrollment Changes",
     "Mid-year benefits changes are permitted only following a verified qualifying life event (e.g., marriage, birth, or spouse coverage change). Documentation must be submitted within 30 days.",
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

# --------------------------------------------------
# 4. Synthetic employee names
# --------------------------------------------------

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


def clear_existing_data(connection):
    """Safely clear tables in child-to-parent order to respect foreign key constraints."""
    tables_in_order = [
        "TicketPolicyCitation",
        "TicketEvent",
        "Resolution",
        "SLA",
        "Assignment",
        "Message",
        "Ticket",
        "KnowledgeArticle",
        "PolicyVersion",
        "PolicyDocument",
        "Employee",
        "Category",
        "Department",
    ]
    for table in tables_in_order:
        connection.execute(f"DELETE FROM {table}")


def generate_master_data(db_path=None):
    target_db = Path(db_path) if db_path else DB_PATH

    if not target_db.exists():
        raise FileNotFoundError(
            f"Database not found at {target_db}. Run src/init_db.py first."
        )

    connection = sqlite3.connect(target_db)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        with connection:
            clear_existing_data(connection)

            # 1. Departments
            connection.executemany("""
                INSERT INTO Department (department_id, department_name, default_queue)
                VALUES (?, ?, ?)
            """, DEPARTMENTS)

            # 2. Categories
            connection.executemany("""
                INSERT INTO Category (category_id, category_name, default_queue, priority)
                VALUES (?, ?, ?, ?)
            """, CATEGORIES)

            # 3. Employees (100 synthetic employees)
            department_ids = [d[0] for d in DEPARTMENTS]
            employees = []
            for i in range(1, EMPLOYEE_COUNT + 1):
                employee_id = f"EMP-{i:06d}"
                first = FIRST_NAMES[(i - 1) % len(FIRST_NAMES)]
                last = LAST_NAMES[((i - 1) // len(FIRST_NAMES)) % len(LAST_NAMES)]
                full_name = f"{first} {last} {i:03d}"
                department_id = department_ids[(i - 1) % len(department_ids)]

                # First 5 employees are managers across departments
                manager_id = None if i <= 5 else f"EMP-{((i - 6) % 5) + 1:06d}"
                audience = "Manager" if i <= 5 else "Employee"
                employment_status = (
                    "Onboarding" if i % 17 == 0
                    else "Inactive" if i % 23 == 0
                    else "Active"
                )

                employees.append((
                    employee_id,
                    full_name,
                    department_id,
                    manager_id,
                    employment_status,
                    audience,
                    "2026-01-01T09:00:00Z",
                ))

            connection.executemany("""
                INSERT INTO Employee (
                    employee_id, full_name, department_id, manager_id,
                    employment_status, audience, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, employees)

            # 4. Policy Documents and Versions
            policy_rows = []
            version_rows = []

            for i, (category, title, text, audience) in enumerate(POLICY_TEMPLATES, start=1):
                policy_id = f"POL-HR-2026-{i:03d}"
                category_id = CATEGORY_ID_BY_NAME[category]

                owner_department_id = (
                    "DPT-003" if category == "Payroll"
                    else "DPT-002" if category == "Onboarding" and title == "Account Provisioning"
                    else "DPT-001"
                )

                policy_rows.append((
                    policy_id,
                    title,
                    category_id,
                    owner_department_id,
                    audience,
                    "2026-01-01T09:00:00Z",
                ))

                # For policies 1 to 18:
                # Version 1 is Retired (2026-01-01 to 2026-03-31)
                # Version 2 is Published (2026-04-01 to None)
                # For policies 19 and 20:
                # Version 1 is Published (2026-01-01 to None)
                # Version 2 is Draft (2027-01-01 to None) -> tests date and status selection!
                if i <= 18:
                    version_rows.append((
                        f"VER-{policy_id}-01",
                        policy_id,
                        1,
                        "2026-01-01",
                        "2026-03-31",
                        f"[Historical Q1 Policy] {text}",
                        "Retired",
                        "2026-01-01T09:00:00Z",
                    ))
                    version_rows.append((
                        f"VER-{policy_id}-02",
                        policy_id,
                        2,
                        "2026-04-01",
                        None,
                        f"[Current Active Policy] {text}",
                        "Published",
                        "2026-04-01T09:00:00Z",
                    ))
                else:
                    version_rows.append((
                        f"VER-{policy_id}-01",
                        policy_id,
                        1,
                        "2026-01-01",
                        None,
                        f"[Current Active Policy] {text}",
                        "Published",
                        "2026-01-01T09:00:00Z",
                    ))
                    version_rows.append((
                        f"VER-{policy_id}-02",
                        policy_id,
                        2,
                        "2027-01-01",
                        None,
                        f"[Upcoming Draft Revision] {text}",
                        "Draft",
                        "2026-10-01T09:00:00Z",
                    ))

            connection.executemany("""
                INSERT INTO PolicyDocument (
                    policy_id, title, category_id, owner_department_id,
                    audience, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, policy_rows)

            connection.executemany("""
                INSERT INTO PolicyVersion (
                    version_id, policy_id, version_number, effective_from,
                    effective_to, policy_text, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, version_rows)

            # 5. Knowledge Articles (150 articles, each citing an active published version)
            article_rows = []
            for i in range(1, ARTICLE_COUNT + 1):
                template_index = (i - 1) % len(POLICY_TEMPLATES)
                category, title, policy_text, _ = POLICY_TEMPLATES[template_index]
                policy_num = template_index + 1
                policy_id = f"POL-HR-2026-{policy_num:03d}"

                # Link to the Published version
                version_id = f"VER-{policy_id}-02" if policy_num <= 18 else f"VER-{policy_id}-01"
                category_id = CATEGORY_ID_BY_NAME[category]

                article_rows.append((
                    f"KB-{i:06d}",
                    f"{title} — Guidance Note #{i:03d}",
                    f"Summary: {policy_text[:120]}... Refer to full policy for comprehensive steps.",
                    category_id,
                    version_id,
                    "Published",
                    "2026-04-01T09:00:00Z",
                ))

            connection.executemany("""
                INSERT INTO KnowledgeArticle (
                    article_id, title, snippet, category_id, version_id,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, article_rows)

        # Validate master data
        validate_master_data(connection)

    finally:
        connection.close()


def validate_master_data(connection):
    expected_counts = {
        "Department": len(DEPARTMENTS),
        "Category": len(CATEGORIES),
        "Employee": EMPLOYEE_COUNT,
        "PolicyDocument": POLICY_COUNT,
        "PolicyVersion": POLICY_COUNT * 2,
        "KnowledgeArticle": ARTICLE_COUNT,
    }

    print("\nMASTER DATA VALIDATION")
    print("-" * 35)

    for table, expected in expected_counts.items():
        actual = connection.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

        print(f"{table}: {actual} rows (expected {expected})")
        if actual != expected:
            raise ValueError(
                f"{table}: expected {expected}, found {actual}."
            )

    violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise ValueError(f"Foreign-key violations: {violations}")

    # Every knowledge article must reference an existing policy version
    missing_versions = connection.execute("""
        SELECT COUNT(*)
        FROM KnowledgeArticle k
        LEFT JOIN PolicyVersion p ON k.version_id = p.version_id
        WHERE p.version_id IS NULL
    """).fetchone()[0]
    if missing_versions > 0:
        raise ValueError("Knowledge articles reference non-existent policy versions.")

    # Published articles must reference published policy versions
    invalid_articles = connection.execute("""
        SELECT COUNT(*)
        FROM KnowledgeArticle k
        JOIN PolicyVersion p ON k.version_id = p.version_id
        WHERE k.status = 'Published' AND p.status <> 'Published'
    """).fetchone()[0]
    if invalid_articles > 0:
        raise ValueError("Published articles reference non-published policy versions.")

    print("\nForeign-key integrity: PASS")
    print("Published article version checks: PASS")
    print("Master data generation completed successfully!")


if __name__ == "__main__":
    generate_master_data()
