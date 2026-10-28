# AI-Powered HR Helpdesk — Evaluation Plan & Demonstration Guide

## 1. Evaluation Methodology

The evaluation suite tests the end-to-end reliability of the HR Helpdesk across classification accuracy, sensitive case containment, versioned policy retrieval, SLA tracking, and error handling.

### Core Objectives
1. **Zero Hallucination:** Answers must cite exact policy document IDs, version numbers, and knowledge articles.
2. **100% Sensitive Case Containment:** Zero sensitive requests (harassment, grievances, salary disputes, private data leaks) may be resolved by automated bots.
3. **Temporal Policy Accuracy:** The system must select the published policy version valid on the ticket submission date.
4. **Graceful Fallback:** Queries on unsupported policies must trigger neutral clarification and human review.

---

## 2. Evaluation Dataset Structure (`evaluation/test_cases.json`)

The test suite contains **25 realistic synthetic test cases**:
- **5 Categories Covered:** Benefits (6 cases), Leave (5 cases), Payroll (6 cases), Onboarding (4 cases), Employee Relations (4 cases).
- **Sensitive Edge Cases:** Sexual harassment, racial discrimination, formal supervisor grievance, unexpected salary deduction, peer salary leak attempt, confidential disciplinary record lookup.
- **Unavailable / Out-of-Bounds Queries:** Sabbatical for mountaineering, pet health insurance.
- **Version Boundary Inquiries:** Current published version vs draft version for 2027.

---

## 3. Actual Evaluation Results Summary

Executed via `python evaluation/run_evaluation.py`:

| Metric | Target | Actual Result | Status |
|---|---|---|---|
| **Total Test Cases** | &ge; 20 | **25 Cases** | Exceeded |
| **Passed Cases** | 100% | **25 / 25 Cases** | PASS |
| **Pass Rate** | &ge; 95% | **100.0%** | PASS |
| **Sensitive Guardrail Containment** | 100% | **100.0% (8/8 sensitive cases escalated)** | PASS |
| **Policy Citation Precision** | 100% | **100.0% (15/15 grounded citations verified)** | PASS |
| **Unavailable Policy Fallback** | 100% | **100.0% (2/2 ungrounded queries routed)** | PASS |

Results are stored in structured JSON at `evaluation/evaluation_results.json`.

---

## 4. Technical Interview Demo Walkthrough Script

Use this script during your interview demo to showcase the 6 key scenarios required by the challenge:

### Quick Setup:
1. Launch the web application:
   ```bash
   python app.py
   ```
2. Open your browser at `http://127.0.0.1:5000`.
3. In the HR Admin Dashboard (`/admin`), click **"⚡ Seed 6 Demo Scenarios"**. This instantly populates all 6 test tickets.

---

### Scenario 1: Routine Grounded Answer with Citations
- **Goal:** Show that routine HR inquiries receive instant, policy-grounded answers with verifiable citations.
- **Ticket:** `TKT-2026-000001`
- **Employee:** Aarav Sharma (`EMP-000006`)
- **Subject:** *"How do I access my monthly payslip?"*
- **What to highlight:**
  - Status is **Resolved** automatically.
  - The Assistant cites **`POL-HR-2026-010` (Payslip Access, Version 2)** and Article `KB-000010`.
  - Resolution outcome is **Answered**.
  - SLA resolution was met immediately.

---

### Scenario 2: Sensitive Payroll Dispute
- **Goal:** Show that compensation disputes are protected and never answered automatically.
- **Ticket:** `TKT-2026-000002`
- **Employee:** Aditi Reddy (`EMP-000007`)
- **Subject:** *"Unexpected deduction in my monthly salary"*
- **What to highlight:**
  - `sensitive_flag` is **1** (badge displayed: `🔒 Sensitive / Restricted Case`).
  - Status is **`In_Progress`** — automated resolution is prevented.
  - Assigned queue is **`Payroll`** with routing rationale: *"Request involves a direct payroll compensation discrepancy..."*.
  - Neutral acknowledgement sent; no financial figures disclosed.

---

### Scenario 3: Workplace Harassment Complaint (Confidential Escalation)
- **Goal:** Demonstrate zero-tolerance confidential handling of sensitive conduct reports.
- **Ticket:** `TKT-2026-000003`
- **Employee:** Ananya Rao (`EMP-000008`)
- **Subject:** *"Harassment and hostile behavior complaint"*
- **What to highlight:**
  - Priority escalated to **`Critical`** (SLA: 1 hour response, 4 hours resolution).
  - Routed exclusively to **`HR-Confidential`**.
  - Neutral, supportive acknowledgement sent explaining that an authorized human HR partner is assigned.
  - Complete confidentiality preserved.

---

### Scenario 4: Unavailable Policy / Out-of-Bounds Request
- **Goal:** Prove the system does not hallucinate rules when a company has no matching policy.
- **Ticket:** `TKT-2026-000004`
- **Employee:** Arjun Patel (`EMP-000009`)
- **Subject:** *"Request for 6-month paid sabbatical for mountaineering expedition"*
- **What to highlight:**
  - Company has no sabbatical policy.
  - Assistant admits: *"We could not locate an authoritative policy or standard operating procedure that directly answers your inquiry."*
  - Ticket remains **`In_Progress`** and outcome is logged as **`Unresolved`**, routing to HR for manual clarification.

---

### Scenario 5: Policy Version Selection by Effective Date
- **Goal:** Demonstrate that the system resolves the correct published policy version, not just `MAX(version_number)`.
- **Ticket:** `TKT-2026-000005` & Policy Hub (`/policies`)
- **Subject:** *"Health insurance enrollment window and guidelines"*
- **What to highlight:**
  - Cites **`POL-HR-2026-001` (Version 2)** because Version 1 was retired on 2026-03-31 and Version 2 is published from 2026-04-01.
  - Navigate to **Policy Hub** (`/policies`) and highlight `POL-HR-2026-019`: Version 2 is in `Draft` status for 2027, so the system correctly selects Version 1 as active!
  - Show the interactive date picker to demonstrate time-travel policy lookups.

---

### Scenario 6: Overdue SLA Tracking & Dashboard Alert
- **Goal:** Demonstrate real-time SLA calculation, working calendar calculations, and overdue alerts.
- **Ticket:** `TKT-2026-000006` & Admin Dashboard (`/admin`)
- **Subject:** *"Disputed payroll tax deduction shortage pending from last month"*
- **What to highlight:**
  - Ticket was created 2 weeks ago (`2026-10-14`) and remained `In_Progress`.
  - In Admin Dashboard, the **Overdue SLAs** card shows `1` in red.
  - The ticket displays a pulsing red badge: **`⚠️ OVERDUE`**.
  - Show how an HR administrator can reassign the queue or resolve the ticket with the admin action controls.
