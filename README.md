# AI-Powered HR Helpdesk

> **YottaFlex AI Forward Deployed Engineer (FDE) Code Challenge**  
> A complete, fully-tested, full-stack HR Helpdesk that resolves routine employee requests using versioned policy sources, enforces strict confidentiality and routing for sensitive cases, and tracks service-level agreements (SLAs).

---

## Table of Contents
1. [Business Problem & Overview](#1-business-problem--overview)
2. [System Architecture & Role-Based Portals](#2-system-architecture--role-based-portals)
3. [Database Design & Relationships](#3-database-design--relationships)
4. [Role-Based Access Control (RBAC) & Portal Features](#4-role-based-access-control-rbac--portal-features)
5. [Policy Versioning & Effective Date Approach](#5-policy-versioning--effective-date-approach)
6. [Ticket Lifecycle Workflow](#6-ticket-lifecycle-workflow)
7. [Sensitive-Case Detection & Guardrails](#7-sensitive-case-detection--guardrails)
8. [SLA Management & Business Calendar](#8-sla-management--business-calendar)
9. [Setup & Installation Instructions (Windows & VS Code)](#9-setup--installation-instructions-windows--vs-code)
10. [Running the Application](#10-running-the-application)
11. [Running Automated Tests](#11-running-automated-tests)
12. [Running the Evaluation Benchmark](#12-running-the-evaluation-benchmark)
13. [Interview Demonstration Walkthrough (6 Core Scenarios)](#13-interview-demonstration-walkthrough-6-core-scenarios)
14. [Environment Variables](#14-environment-variables)
15. [Security, Disclaimers & Known Limitations](#15-security-disclaimers--known-limitations)

---

## 1. Business Problem & Overview

Modern enterprise HR teams spend significant time answering repetitive inquiries regarding leave balances, insurance enrollment, and payslips, while urgent, confidential cases (such as workplace harassment or payroll disputes) require human review.

This application provides an end-to-end HR Helpdesk that:
1. **Classifies employee requests** across 5 categories (*Benefits*, *Leave*, *Payroll*, *Onboarding*, *Employee Relations*).
2. **Detects sensitive cases** (harassment, grievances, salary discrepancies, unauthorized third-party record queries) and prevents automated resolution.
3. **Retrieves applicable published policy versions** based on effective dates, returning grounded answers with verifiable citations to policy documents, versions, and knowledge articles.
4. **Handles missing/out-of-bounds policy questions** without hallucination, routing them to human specialists for clarification.
5. **Enforces SLAs** using working business calendars (skipping weekends and off-hours) and highlights overdue tickets on an admin dashboard.
6. **Maintains a complete audit trail** with append-only messages, assignment histories, and status transition events.

---

## 2. System Architecture

The project is structured with modular, single-responsibility services:

```
hr helpdesk/
    app.py                     # Flask application routes and UI controllers
    requirements.txt           # Python dependencies
    README.md                  # Comprehensive documentation and setup guide
    .env.example               # Template environment configuration
    .gitignore                 # Git ignore rules
    src/
        init_db.py             # Schema initialisation script
        check_db.py            # Database health & FK verification utility
        generate_master_data.py# Deterministic generator (5 depts, 100 emps, 20 policies, 40 versions, 150 KBs)
        database.py            # SQLite connection factory & transaction managers
        classifier.py          # Category classifier & sensitive-case detection
        policy_retrieval.py    # Policy version resolver & grounded knowledge retriever
        response_service.py    # Grounded answer & neutral escalation message generator
        ticket_service.py      # Ticket lifecycle, assignment history & KPI aggregations
        sla_service.py         # Business calendar arithmetic & SLA tracking
    sql/
        schema.sql             # Relational DDL schema (13 tables, strict FKs)
    templates/
        base.html              # Layout shell with navigation & simulated demo identity
        employee_home.html     # Employee self-service portal & ticket history
        new_ticket.html        # New ticket submission form with topic suggestions
        ticket_detail.html     # Conversation timeline, citations, SLAs & admin actions
        admin_dashboard.html   # HR admin KPI dashboard, queue filters & overdue alerts
        policy_list.html       # Policy version viewer with interactive date picker
    static/
        css/styles.css         # Responsive enterprise design system
        js/app.js              # Client-side UI interactions & auto-dismiss alerts
    data/
        hr_helpdesk.db         # Persistent SQLite database
    docs/
        architecture.md        # Architectural diagrams & component interactions
        data_dictionary.md     # Full data dictionary for all 13 tables
        evaluation_plan.md     # Evaluation methodology & interview demo walkthrough
    tests/
        conftest.py            # Pytest fixtures with isolated temporary databases
        test_database.py       # Master data, record counts & FK integrity tests
        test_classification.py # Category classification & sensitive routing tests
        test_policy_retrieval.py# Version date selection & grounded citation tests
        test_tickets.py        # Ticket creation, lifecycle & audit trail tests
        test_sla.py            # SLA targets, business hours & dashboard metrics tests
    evaluation/
        test_cases.json        # 25 evaluation test requests with ground truth
        run_evaluation.py      # Automated benchmark execution script
        evaluation_results.json# Structured benchmark results (100% pass rate)
```

---

## 3. Database Design & Relationships

The database is built on SQLite with `PRAGMA foreign_keys = ON` enforced on every transaction:

| Table | Description |
|---|---|
| **Department** | 5 corporate departments and their default queues. |
| **Employee** | 100 synthetic employees with manager hierarchies and status checks. |
| **Category** | 5 HR categories (*Benefits*, *Leave*, *Payroll*, *Onboarding*, *Employee Relations*). |
| **PolicyDocument** | 20 master policy documents with department owners and audience restrictions. |
| **PolicyVersion** | 40 immutable policy versions (*Published*, *Retired*, *Draft*) with date ranges. |
| **KnowledgeArticle** | 150 searchable guidance articles linked to published policy versions. |
| **Ticket** | Employee requests with status, priority, sensitive flag, and timestamps. |
| **Message** | Append-only conversation thread between Employee, Assistant, and HR. |
| **Assignment** | Complete routing history tracking queues, assignees, and timestamps. |
| **SLA** | Priority-based response and resolution targets with compliance status. |
| **Resolution** | Ticket outcomes (*Answered*, *Escalated*, *Unresolved*) and summaries. |
| **TicketPolicyCitation** | Bridge table linking tickets to cited versions and knowledge articles. |
| **TicketEvent** | Append-only audit trail capturing every status transition and rationale. |

---

## 4. Role-Based Access Control (RBAC) & Portal Features

The application features role-based interfaces distinguishing the **Employee Portal** and the **HR / Admin Portal**:

### Portal Comparison Matrix

| Capability | Employee Portal (`/employee`) | HR / Admin Portal (`/admin`) |
|---|:---:|:---:|
| **Target Users** | All Employees | HR Partners, IT/Operations, Administrators |
| **Ticket Visibility** | **Strictly Isolated:** Only tickets personally submitted | **Global:** All company tickets across all queues |
| **Submit Requests** | Yes (Instant AI Grounding) | Yes (for demonstration) |
| **Grounded AI Answers & Citations** | Yes (Verifiable policy version citations) | Yes |
| **Ticket Lifecycle Controls** | Read-only status & reply | Status transition & outcome recording |
| **Queue Reassignment** | No | Yes (Benefits, Leave, Payroll, Confidential, etc.) |
| **Confidential Internal Notes** | **Strictly Hidden** | Yes (Private staff investigation notes) |
| **SLA & Overdue Compliance** | Personal ticket SLA targets | Global SLA KPI dashboard & breach tracking |
| **Restricted Master Data** | Personal profile only | Full employee master data & reporting lines |

### Security & Privacy Protections
1. **Ticket Isolation:** When logged in as an Employee, attempting to view any ticket belonging to another employee (`/tickets/<ticket_id>`) is blocked with HTTP 403 / redirection warning.
2. **Internal HR Notes Guardrail:** Staff notes tagged with `[INTERNAL NOTE]` are completely stripped from employee portal responses and only rendered to authorized HR/Admin users with a distinctive yellow warning badge.
3. **1-Click Demo Personas:** The landing page (`/login`) provides quick presets:
   - `👤 Employee: Ishaan Sharma (EMP-000006)`
   - `👤 Employee: Kavya Sharma (EMP-000007)`
   - `👔 HR Partner: Aarav Sharma (EMP-000001)`
   - `💻 IT Partner: Aditi Sharma (EMP-000002)`
   - `⚡ System Administrator`

---

## 5. Policy Versioning & Effective Date Approach

Company policies change over time. The application resolves the applicable policy version dynamically based on ticket submission time:

```sql
SELECT pv.*
FROM PolicyVersion pv
WHERE pv.policy_id = :policy_id
  AND pv.status = 'Published'
  AND pv.effective_from <= :ticket_date
  AND (pv.effective_to IS NULL OR pv.effective_to >= :ticket_date)
ORDER BY pv.version_number DESC
LIMIT 1;
```

### Deterministic Master Data Configuration:
- **Policies 1 to 18:** Version 1 was active during Q1 (`2026-01-01` to `2026-03-31`, status: `Retired`). Version 2 took effect `2026-04-01` (status: `Published`). For current requests, Version 2 is selected.
- **Policies 19 & 20:** Version 1 is currently active (`2026-01-01`, status: `Published`). Version 2 is an upcoming draft for 2027 (`2027-01-01`, status: `Draft`). The system **correctly selects Version 1**, proving it does not blindly choose `MAX(version_number)`.

---

## 6. Ticket Lifecycle Workflow

The system supports 5 defined statuses:

```
[Open] ──► [In_Progress] ──► [Resolved] ──► [Closed]
              ▲   │
              │   ▼
        [Awaiting_Employee]
```

1. **Ticket Ingestion:** When a ticket is submitted, the employee's request is recorded as Message #1 (`Request`).
2. **Classification & Guardrail Check:**
   - If **routine and grounded:** The AI Helpdesk generates a grounded answer citing the policy and article as Message #2 (`Answer`), records `TicketPolicyCitation`, sets status to `Resolved`, and marks `resolution_met = 1`.
   - If **sensitive:** The ticket is flagged (`sensitive_flag = 1`), assigned to `HR-Confidential` or `Payroll`, an escalation acknowledgement is recorded as Message #2 (`Escalation`), and the status is set to `In_Progress` (never auto-resolved).
   - If **ungrounded/unsupported:** An ungrounded clarification message is recorded as Message #2 (`Clarification`), and the ticket is set to `In_Progress` for manual review.
3. **Audit History:** Every transition is written to `TicketEvent` with `old_status`, `new_status`, reason, and timestamp.
4. **Reassignment:** When a ticket is reassigned, the prior assignment is closed (`ended_at = now`) and a new assignment is inserted, preserving complete historical lineage.

---

## 7. Sensitive-Case Detection & Guardrails

The system implements rule-based pattern matching with conservative fallback guardrails:

| Sensitive Category | Triggers & Examples | Assigned Queue | Priority | Behavior |
|---|---|---|---|---|
| **Harassment / Discrimination** | Harassment, sexual harassment, hostile work environment, racial/gender bias, retaliation, abuse. | `HR-Confidential` | **Critical** | Zero auto-resolution. Immediate confidential escalation. |
| **Employee Grievance** | Formal complaint against supervisor, managerial misconduct, wrongful termination threat, unfair treatment. | `HR-Confidential` | **High** | Routed to senior HR partner for private mediation. |
| **Salary Discrepancy** | Unexpected deduction, paycheck shortage, underpayment dispute, missing bonus/commission. | `Payroll` | **High** | Routed to Payroll specialists; no financial details leaked in public queues. |
| **Third-Party Privacy** | Attempting to look up a coworker's salary, home address, medical condition, or disciplinary record. | `HR-Confidential` | **High** | Immediate red flag; unauthorized disclosure blocked. |

---

## 8. SLA Management & Business Calendar

### Target Deadlines by Priority
- **Critical:** 1-hour Response SLA, 4-hour Resolution SLA.
- **High:** 4-hour Response SLA, 24-hour Resolution SLA.
- **Medium:** 8-hour Response SLA, 48-hour Resolution SLA.
- **Low:** 24-hour Response SLA, 72-hour Resolution SLA.

### Working Calendar Engine
- Default calendar: **Standard Business Hours (09:00 - 17:00 Mon-Fri UTC)**.
- If a ticket arrives Friday at 16:30 UTC with an 8-hour SLA:
  - 30 minutes are consumed on Friday (16:30 - 17:00).
  - Saturday and Sunday are skipped.
  - The remaining 7.5 hours are added starting Monday at 09:00 UTC &rarr; deadline is **Monday 16:30 UTC**.
- Overdue tickets (open tickets past `resolution_due_at`) are flagged with a pulsing red badge on the dashboard.

---

## 9. Setup & Installation Instructions (Windows & VS Code)

### Prerequisites
- Windows 10/11
- Python 3.10+ (Verified on Python 3.13)
- VS Code (Recommended)
- PowerShell or Command Prompt

### Step 1: Open the Project in VS Code
Open VS Code, press `Ctrl + O`, and select folder:
```
C:\Users\Admin\OneDrive\Documents\hr helpdesk
```
Open a new integrated terminal (`Ctrl + \``).

### Step 2: (Optional) Create & Activate Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Step 3: Install Required Dependencies
```powershell
pip install -r requirements.txt
```
*(Only lightweight packages: `flask` and `pytest`).*

### Step 4: Initialize the SQLite Database & Generate Master Data
```powershell
python src/init_db.py
python src/generate_master_data.py
```
*Output confirms 13 tables created, 100 employees, 20 policies, 40 versions, and 150 knowledge articles with 100% foreign-key integrity.*

---

## 10. Running the Application

Start the Flask development server:
```powershell
python app.py
```

Open your browser and navigate to:
- **Role Selection / Login Page:** [http://127.0.0.1:5000/login](http://127.0.0.1:5000/login)
- **Employee Portal:** [http://127.0.0.1:5000/employee](http://127.0.0.1:5000/employee)
- **HR Admin Dashboard:** [http://127.0.0.1:5000/admin](http://127.0.0.1:5000/admin)
- **Policy Hub & Versioning:** [http://127.0.0.1:5000/policies](http://127.0.0.1:5000/policies)

---

## 11. Running Automated Tests

Run the complete test suite with verbose output:
```powershell
python -m pytest -v
```

### Actual Test Results (36/36 Passed)
```
tests/test_classification.py::test_classify_all_five_categories PASSED
tests/test_classification.py::test_sensitive_harassment_detection PASSED
tests/test_classification.py::test_sensitive_discrimination_detection PASSED
tests/test_classification.py::test_sensitive_grievance_detection PASSED
tests/test_classification.py::test_sensitive_payroll_dispute_detection PASSED
tests/test_classification.py::test_sensitive_third_party_private_info_detection PASSED
tests/test_classification.py::test_priority_escalation_for_urgent_routine_request PASSED
tests/test_database.py::test_master_data_record_counts PASSED
tests/test_database.py::test_foreign_key_integrity PASSED
tests/test_database.py::test_master_data_repeat_execution_idempotency PASSED
tests/test_database.py::test_all_twenty_policies_exist PASSED
tests/test_database.py::test_knowledge_articles_cite_published_versions PASSED
tests/test_database.py::test_parameterized_volume_generation_and_anomalies PASSED
tests/test_policy_retrieval.py::test_retrieval_payslip_access PASSED
tests/test_policy_retrieval.py::test_retrieval_sick_leave_policy PASSED
tests/test_policy_retrieval.py::test_effective_date_version_selection_does_not_just_take_max_number PASSED
tests/test_policy_retrieval.py::test_effective_date_retired_version_not_selected_for_current_date PASSED
tests/test_policy_retrieval.py::test_grounded_answer_includes_citations PASSED
tests/test_policy_retrieval.py::test_fallback_when_no_policy_found PASSED
tests/test_rbac_and_portals.py::test_portal_selection_page_renders_both_portals PASSED
tests/test_rbac_and_portals.py::test_employee_login_and_dashboard_access PASSED
tests/test_rbac_and_portals.py::test_employee_cannot_access_admin_dashboard PASSED
tests/test_rbac_and_portals.py::test_hr_partner_can_access_admin_dashboard PASSED
tests/test_rbac_and_portals.py::test_strict_employee_ticket_isolation PASSED
tests/test_rbac_and_portals.py::test_internal_hr_notes_hidden_from_employee_portal PASSED
tests/test_rbac_and_portals.py::test_employee_dashboard_search_and_filters PASSED
tests/test_sla.py::test_sla_targets_by_priority PASSED
tests/test_sla.py::test_business_calendar_skips_weekends PASSED
tests/test_sla.py::test_evaluate_sla_status_overdue_flag PASSED
tests/test_sla.py::test_dashboard_summary_calculations PASSED
tests/test_tickets.py::test_create_routine_ticket_success PASSED
tests/test_tickets.py::test_sensitive_ticket_never_auto_resolved PASSED
tests/test_tickets.py::test_create_ticket_invalid_employee_raises_error PASSED
tests/test_tickets.py::test_ticket_reassignment_preserves_history PASSED
tests/test_tickets.py::test_ticket_status_transition_and_event_trail PASSED
tests/test_tickets.py::test_add_message_increments_sequence PASSED

============================= 36 passed in 8.67s ==============================
```

---

## 12. Running the Evaluation Benchmark

Execute the 25-case evaluation benchmark:
```powershell
python evaluation/run_evaluation.py
```

### Actual Benchmark Output (25/25 Passed, 100.0%)
```
===========================================================================
RUNNING AI HR HELPDESK EVALUATION SUITE (25 TEST CASES)
===========================================================================

[PASS] TC-001: Payslip Portal Access
[PASS] TC-002: Unexpected Salary Deduction
[PASS] TC-003: Workplace Harassment Complaint
[PASS] TC-004: Unavailable Policy (Mountaineering Sabbatical)
[PASS] TC-005: Applicable Policy Version Selection (Health Insurance)
[PASS] TC-006: Sick Leave Medical Certificate Requirement
[PASS] TC-007: Annual Leave Accrual Rate
[PASS] TC-008: Public Holiday Calendar Location
[PASS] TC-009: Salary Disbursement Schedule
[PASS] TC-010: Bank Account Update Deadline
[PASS] TC-011: New Hire Onboarding Checklist
[PASS] TC-012: IT Hardware and Equipment Replacement
[PASS] TC-013: Account Credentials Provisioning
[PASS] TC-014: Orientation Meeting Logistics
[PASS] TC-015: Dependent Health Coverage Addition
[PASS] TC-016: Physical Insurance Card Delivery
[PASS] TC-017: Racial Discrimination Report
[PASS] TC-018: Formal Supervisor Grievance
[PASS] TC-019: Peer Private Salary Lookup Attempt
[PASS] TC-020: Confidential Disciplinary Records Access
[PASS] TC-021: Missing Sales Bonus Dispute
[PASS] TC-022: Mid-Year Benefits Enrollment Changes
[PASS] TC-023: Leave Balance Portal Location
[PASS] TC-024: Policy Version Boundary (Draft vs Published)
[PASS] TC-025: Out of Bounds Pet Health Insurance

---------------------------------------------------------------------------
EVALUATION SUMMARY: 25/25 PASSED (100.0%)
Results written to: evaluation/evaluation_results.json
---------------------------------------------------------------------------
```

---

## 13. Interview Demonstration Walkthrough (6 Core Scenarios)

In the Admin Dashboard (`/admin`), click **"⚡ Seed 6 Demo Scenarios"**. This seeds the 6 required scenarios:

| # | Scenario | Ticket ID | Key Behavior to Demonstrate in Interview |
|---|---|---|---|
| **1** | **Routine Grounded Answer** | `TKT-2026-000001` | Employee asks how to access a payslip. System answers immediately citing `POL-HR-2026-010` (v2) and `KB-000010`. Status: **Resolved**. |
| **2** | **Salary Dispute** | `TKT-2026-000002` | Employee reports unexpected $450 deduction. Flagged `sensitive_flag = 1`, routed to `Payroll`, neutral acknowledgement given. Status: **In_Progress** (no auto-resolution). |
| **3** | **Harassment Report** | `TKT-2026-000003` | Employee reports ongoing workplace harassment. Flagged as **Critical** priority, routed to `HR-Confidential`, strict privacy preserved. Status: **In_Progress**. |
| **4** | **Unavailable Policy** | `TKT-2026-000004` | Employee asks for 6-month paid mountaineering sabbatical. System does not hallucinate; states policy is unavailable and routes to HR. Outcome: **Unresolved**. |
| **5** | **Policy Version Selection** | `TKT-2026-000005` | Inquiries on Health Insurance cite Version 2 (Published) rather than Version 1 (Retired). In Policy Hub, show that policies 19 & 20 select Version 1 over Version 2 (Draft). |
| **6** | **Overdue SLA Alert** | `TKT-2026-000006` | A pending tax dispute created 2 weeks ago is flagged with a red **`⚠️ OVERDUE`** badge on the dashboard, demonstrating working calendar tracking. |

---

## 14. Environment Variables

Copy `.env.example` to `.env` to configure optional overrides:

```env
# Optional external LLM provider: NONE (default rule-based fallback), OPENAI, ANTHROPIC, GEMINI
LLM_PROVIDER=NONE
LLM_API_KEY=
LLM_MODEL=

FLASK_ENV=development
SECRET_KEY=yottaflex-fde-demo-secret-key-2026
DATABASE_PATH=data/hr_helpdesk.db
BUSINESS_CALENDAR=standard_business_hours
```

---

## 15. Security, Disclaimers & Known Limitations

1. **Synthetic Data Disclaimer:** All employees, manager hierarchies, departments, and policies are 100% synthetic for demonstration purposes.
2. **Authentication Notice:** The application features role-based access control with session isolation and demo identity presets suitable for hackathon demonstrations.
3. **Deterministic Local AI Engine:** The application functions 100% locally with zero paid API keys or external network dependencies.
4. **Future Enhancements:** Vector embeddings (e.g. `sqlite-vec`), enterprise SAML/SSO integration, and bidirectional email webhook integrations.
