# HR Helpdesk — Comprehensive Data Dictionary & Relational Specification

This data dictionary defines all 13 core relational entities, cardinality specifications, foreign-key relationships, lifecycle states, validation constraints, and anomaly tracking labels for the AI-Powered HR Helpdesk.

---

## 1. Relational Schema & Cardinality Matrix

| Parent Entity | Relationship | Child Entity | Cardinality | Enforced Foreign Key | Nullable? | Cascade Rule |
|---|---|---|---|---|---|---|
| **Department** | employs | **Employee** | 1 : N | `Employee.department_id -> Department.department_id` | No | RESTRICT |
| **Department** | owns | **PolicyDocument** | 1 : N | `PolicyDocument.owner_department_id -> Department.department_id` | No | RESTRICT |
| **Category** | groups | **PolicyDocument** | 1 : N | `PolicyDocument.category_id -> Category.category_id` | No | RESTRICT |
| **Category** | categorizes | **Ticket** | 1 : N | `Ticket.category_id -> Category.category_id` | No | RESTRICT |
| **Category** | groups | **KnowledgeArticle** | 1 : N | `KnowledgeArticle.category_id -> Category.category_id` | No | RESTRICT |
| **Employee** | manages | **Employee** | 1 : N | `Employee.manager_id -> Employee.employee_id` | Yes (Managers have NULL) | RESTRICT |
| **Employee** | submits | **Ticket** | 1 : N | `Ticket.employee_id -> Employee.employee_id` | No | RESTRICT |
| **PolicyDocument** | versioned by | **PolicyVersion** | 1 : N | `PolicyVersion.policy_id -> PolicyDocument.policy_id` | No | RESTRICT |
| **PolicyVersion** | grounds | **KnowledgeArticle** | 1 : N | `KnowledgeArticle.version_id -> PolicyVersion.version_id` | No | RESTRICT |
| **Ticket** | contains | **Message** | 1 : N | `Message.ticket_id -> Ticket.ticket_id` | No | CASCADE / RESTRICT |
| **Ticket** | routed via | **Assignment** | 1 : N | `Assignment.ticket_id -> Ticket.ticket_id` | No | RESTRICT |
| **Ticket** | governed by | **SLA** | 1 : 1 | `SLA.ticket_id -> Ticket.ticket_id` | No (UNIQUE) | RESTRICT |
| **Ticket** | concludes with | **Resolution** | 1 : 1 | `Resolution.ticket_id -> Ticket.ticket_id` | No (UNIQUE) | RESTRICT |
| **Ticket** | cites | **PolicyVersion** | N : M | Bridge: `TicketPolicyCitation(ticket_id, version_id)` | No | RESTRICT |
| **Ticket** | audited by | **TicketEvent** | 1 : N | `TicketEvent.ticket_id -> Ticket.ticket_id` | No | RESTRICT |

---

## 2. Table-by-Table Field Specifications

### 2.1 Department
Stores organizational departments and their default helpdesk routing queues.

| Field | Type | Required | Allowed Values / Enums | Units / Format | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `department_id` | TEXT | Yes | `DPT-001` to `DPT-005` | `DPT-XXX` | Primary Key | Must match regex `^DPT-\d{3}$` |
| `department_name` | TEXT | Yes | Human Resources, Information Technology, Finance, Engineering, Operations | Text string | Unique | Length between 3 and 100 characters |
| `default_queue` | TEXT | Yes | HR-General, IT-Support, Payroll, Engineering-Operations, Operations | Queue name | Non-unique | Valid queue name |

### 2.2 Employee
Stores synthetic corporate employees and reporting hierarchies.

| Field | Type | Required | Allowed Values / Enums | Units / Format | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `employee_id` | TEXT | Yes | `EMP-000001` to `EMP-000100` | `EMP-XXXXXX` | Primary Key | Must match regex `^EMP-\d{6}$` |
| `full_name` | TEXT | Yes | Synthetic person names | Text string | Non-unique | Non-empty |
| `department_id` | TEXT | Yes | Existing `department_id` | Foreign Key | Non-unique | Must reference valid `Department(department_id)` |
| `manager_id` | TEXT | No | Existing `employee_id` or NULL | Foreign Key | Non-unique | Cannot equal `employee_id` (no self-management) |
| `employment_status` | TEXT | Yes | `'Active'`, `'Inactive'`, `'Onboarding'` | Enum | Non-unique | Must be in allowed enum set |
| `audience` | TEXT | Yes | `'Employee'`, `'Manager'`, `'HR'`, `'IT'` | Enum | Non-unique | Target user role |
| `created_at` | DATETIME | Yes | ISO 8601 UTC timestamp | `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Valid ISO timestamp |

### 2.3 Category
Defines the functional HR inquiry areas, default priority levels, and default queues.

| Field | Type | Required | Allowed Values / Enums | Units / Format | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `category_id` | TEXT | Yes | `CAT-001` to `CAT-005` | `CAT-XXX` | Primary Key | Must match regex `^CAT-\d{3}$` |
| `category_name` | TEXT | Yes | Benefits, Leave, Payroll, Onboarding, Employee Relations | Unique text | Unique | Must match the 5 canonical HR categories |
| `default_queue` | TEXT | Yes | Benefits, Leave, Payroll, Onboarding, HR-Confidential | Queue name | Non-unique | Valid queue name |
| `priority` | TEXT | Yes | `'Low'`, `'Medium'`, `'High'`, `'Critical'` | Priority enum | Non-unique | Must be in allowed enum set |

### 2.4 PolicyDocument
Represents master policy documents independently of their version history.

| Field | Type | Required | Allowed Values / Enums | Units / Format | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `policy_id` | TEXT | Yes | `POL-HR-2026-001` to `POL-HR-2026-020` | `POL-HR-YYYY-XXX` | Primary Key | Must match regex `^POL-HR-\d{4}-\d{3}$` |
| `title` | TEXT | Yes | Official policy title | Text string | Non-unique | Non-empty; max 250 chars |
| `category_id` | TEXT | Yes | Existing `category_id` | Foreign Key | Non-unique | Must reference `Category(category_id)` |
| `owner_department_id` | TEXT | Yes | Existing `department_id` | Foreign Key | Non-unique | Must reference `Department(department_id)` |
| `audience` | TEXT | Yes | `'Employee'`, `'Manager'`, `'HR'`, `'All'` | Enum | Non-unique | Must satisfy `CHECK (audience IN ('Employee', 'Manager', 'HR', 'All'))` |
| `created_at` | DATETIME | Yes | ISO 8601 UTC timestamp | `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Valid ISO timestamp |

### 2.5 PolicyVersion
Stores immutable version snapshots of each policy without overwriting historical text.

| Field | Type | Required | Allowed Values / Enums | Units / Format | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `version_id` | TEXT | Yes | `VER-POL-HR-2026-001-01`, etc. | `VER-<policy_id>-XX` | Primary Key | Must match regex `^VER-POL-HR-\d{4}-\d{3}-\d{2}$` |
| `policy_id` | TEXT | Yes | Existing `policy_id` | Foreign Key | Non-unique | Must reference `PolicyDocument(policy_id)` |
| `version_number` | INTEGER | Yes | Positive integer (&ge; 1) | Sequence int | Unique per policy | `UNIQUE (policy_id, version_number)` |
| `effective_from` | DATE | Yes | ISO Date (`YYYY-MM-DD`) | Date string | Non-unique | Valid date format |
| `effective_to` | DATE | No | ISO Date (`YYYY-MM-DD`) or NULL | Date string | Non-unique | Must be `NULL OR effective_to >= effective_from` |
| `policy_text` | TEXT | Yes | Substantive legal/procedural policy text | Text string | Non-unique | Non-empty |
| `status` | TEXT | Yes | `'Draft'`, `'Published'`, `'Retired'` | Enum | Non-unique | `CHECK (status IN ('Draft', 'Published', 'Retired'))` |
| `created_at` | DATETIME | Yes | ISO 8601 UTC timestamp | `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Valid ISO timestamp |

### 2.6 KnowledgeArticle
Searchable guidance snippets and FAQs grounded in published policy versions.

| Field | Type | Required | Allowed Values / Enums | Units / Format | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `article_id` | TEXT | Yes | `KB-000001` to `KB-000150` | `KB-XXXXXX` | Primary Key | Must match regex `^KB-\d{6}$` |
| `title` | TEXT | Yes | Article summary title | Text string | Non-unique | Non-empty |
| `snippet` | TEXT | Yes | Answer passage | Text string | Non-unique | Non-empty summary |
| `category_id` | TEXT | Yes | Existing `category_id` | Foreign Key | Non-unique | References `Category(category_id)` |
| `version_id` | TEXT | Yes | Existing `version_id` | Foreign Key | Non-unique | References `PolicyVersion(version_id)` (must be Published) |
| `status` | TEXT | Yes | `'Draft'`, `'Published'`, `'Archived'` | Enum | Non-unique | `CHECK (status IN ('Draft', 'Published', 'Archived'))` |
| `created_at` | DATETIME | Yes | ISO 8601 UTC timestamp | `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Valid ISO timestamp |

### 2.7 Ticket
Represents employee helpdesk requests across their lifecycle.

| Field | Type | Required | Allowed Values / Enums | Units / Format | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `ticket_id` | TEXT | Yes | `TKT-2026-000001` to `TKT-2026-005000` | `TKT-YYYY-XXXXXX` | Primary Key | Zero-padded 6 digits |
| `employee_id` | TEXT | Yes | Existing `employee_id` | Foreign Key | Non-unique | References `Employee(employee_id)` |
| `category_id` | TEXT | Yes | Existing `category_id` | Foreign Key | Non-unique | References `Category(category_id)` |
| `subject` | TEXT | Yes | Short summary of inquiry | Text string | Non-unique | Non-empty; max 250 characters |
| `description` | TEXT | Yes | Full request text | Text string | Non-unique | Non-empty |
| `status` | TEXT | Yes | `'Open'`, `'Awaiting_Employee'`, `'In_Progress'`, `'Resolved'`, `'Closed'` | Enum | Non-unique | Valid lifecycle state |
| `priority` | TEXT | Yes | `'Low'`, `'Medium'`, `'High'`, `'Critical'` | Enum | Non-unique | Must be in allowed enum set |
| `sensitive_flag` | INTEGER | Yes | `0` (Standard) or `1` (Sensitive/Confidential) | Binary flag | Non-unique | `CHECK (sensitive_flag IN (0, 1))` |
| `issue_type` | TEXT | No | `'Standard'`, `'obsolete_policy_citation'`, `'sensitive_misrouted'`, `'sla_calendar_anomaly'`, `'unsupported_policy_hallucination'` | Anomaly label | Non-unique | Tracks ground-truth anomaly cases |
| `created_at` | DATETIME | Yes | ISO 8601 UTC timestamp | `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Valid ISO timestamp |
| `updated_at` | DATETIME | Yes | ISO 8601 UTC timestamp | `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Must satisfy `updated_at >= created_at` |

### 2.8 Message
Stores the chronological conversation history for every ticket (4 messages per ticket = 20,000 total).

| Field | Type | Required | Allowed Values / Enums | Units / Format | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `message_id` | TEXT | Yes | `MSG-TKT-2026-000001-001`, etc. | `MSG-<ticket>-XXX` | Primary Key | Unique string |
| `ticket_id` | TEXT | Yes | Existing `ticket_id` | Foreign Key | Non-unique | References `Ticket(ticket_id)` |
| `sequence_number` | INTEGER | Yes | `1`, `2`, `3`, `4` (positive integer) | Sequence int | Unique per ticket | `UNIQUE (ticket_id, sequence_number)` |
| `sender_type` | TEXT | Yes | `'Employee'`, `'Assistant'`, `'HR'`, `'System'` | Enum | Non-unique | `CHECK (sender_type IN ('Employee', 'Assistant', 'HR', 'System'))` |
| `message_text` | TEXT | Yes | Body content | Text string | Non-unique | Non-empty |
| `message_type` | TEXT | Yes | `'Request'`, `'Clarification'`, `'Answer'`, `'Escalation'`, `'Resolution'` | Enum | Non-unique | `CHECK (message_type IN ('Request', 'Clarification', 'Answer', 'Escalation', 'Resolution'))` |
| `created_at` | DATETIME | Yes | ISO 8601 UTC timestamp | `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Valid ISO timestamp |

### 2.9 Assignment
Tracks the full routing lineage, queues, and specialist reassignments.

| Field | Type | Required | Allowed Values / Enums | Units / Format | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `assignment_id` | TEXT | Yes | `ASG-TKT-2026-000001-001`, etc. | `ASG-<ticket>-XXX` | Primary Key | Unique string |
| `ticket_id` | TEXT | Yes | Existing `ticket_id` | Foreign Key | Non-unique | References `Ticket(ticket_id)` |
| `assigned_queue` | TEXT | Yes | Benefits, Leave, Payroll, Onboarding, HR-Confidential, IT-Support, HR-General | Queue name | Non-unique | Valid routing queue |
| `assigned_to` | TEXT | No | Existing `employee_id` or NULL | Foreign Key / Text | Non-unique | Staff identifier |
| `reason` | TEXT | Yes | Explanation of routing decision | Text string | Non-unique | Non-empty audit rationale |
| `assigned_at` | DATETIME | Yes | ISO 8601 UTC timestamp | `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Valid ISO timestamp |
| `ended_at` | DATETIME | No | ISO 8601 UTC timestamp or NULL | `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Must satisfy `ended_at IS NULL OR ended_at >= assigned_at` |

### 2.10 SLA
Stores calculated response and resolution targets and compliance outcomes.

| Field | Type | Required | Allowed Values / Enums | Units / Format | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `sla_id` | TEXT | Yes | `SLA-TKT-2026-000001` | `SLA-<ticket>` | Primary Key | Unique string |
| `ticket_id` | TEXT | Yes | Existing `ticket_id` | Foreign Key | Unique | `ticket_id UNIQUE` (1:1 with Ticket) |
| `policy_name` | TEXT | Yes | e.g. `Critical-Priority Standard SLA` | Rule name | Non-unique | Identifies target rule |
| `response_due_at` | DATETIME | Yes | ISO 8601 UTC timestamp | `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Calculated response target |
| `resolution_due_at` | DATETIME | Yes | ISO 8601 UTC timestamp | `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | `resolution_due_at >= response_due_at` |
| `business_calendar` | TEXT | Yes | `Standard Business Hours (09:00-17:00 Mon-Fri)` | Calendar name | Non-unique | Working calendar identifier |
| `response_met` | INTEGER | No | `0` (Breached), `1` (Met), or NULL (Pending) | Binary int | Non-unique | `CHECK (response_met IN (0, 1))` |
| `resolution_met` | INTEGER | No | `0` (Breached), `1` (Met), or NULL (Pending) | Binary int | Non-unique | `CHECK (resolution_met IN (0, 1))` |

### 2.11 Resolution
Captures the final business outcome, summary, and primary grounding reference.

| Field | Type | Required | Allowed Values / Enums | Units / Format | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `resolution_id` | TEXT | Yes | `RES-TKT-2026-000001` | `RES-<ticket>` | Primary Key | Unique string |
| `ticket_id` | TEXT | Yes | Existing `ticket_id` | Foreign Key | Unique | `ticket_id UNIQUE` (1:1 with Ticket) |
| `outcome` | TEXT | Yes | `'Answered'`, `'Escalated'`, `'Rejected'`, `'Unresolved'` | Enum | Non-unique | `CHECK (outcome IN ('Answered', 'Escalated', 'Rejected', 'Unresolved'))` |
| `resolution_summary` | TEXT | Yes | Final resolution summary | Text string | Non-unique | Non-empty |
| `resolved_at` | DATETIME | No | ISO 8601 UTC timestamp or NULL | `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Set upon resolution |
| `article_id` | TEXT | No | Existing `article_id` or NULL | Foreign Key | Non-unique | References `KnowledgeArticle(article_id)` |
| `version_id` | TEXT | No | Existing `version_id` or NULL | Foreign Key | Non-unique | References `PolicyVersion(version_id)` |

### 2.12 TicketPolicyCitation (Bridge Table)
Many-to-many bridge linking tickets to all policy versions and knowledge articles cited in support of an answer.

| Field | Type | Required | Allowed Values / Enums | Units / Format | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `ticket_id` | TEXT | Yes | Existing `ticket_id` | Foreign Key | Composite PK | References `Ticket(ticket_id)` |
| `version_id` | TEXT | Yes | Existing `version_id` | Foreign Key | Composite PK | References `PolicyVersion(version_id)` |
| `article_id` | TEXT | No | Existing `article_id` or NULL | Foreign Key | Non-unique | References `KnowledgeArticle(article_id)` |
| `cited_at` | DATETIME | Yes | ISO 8601 UTC timestamp | `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Valid timestamp |

Composite Primary Key: `PRIMARY KEY (ticket_id, version_id)`

### 2.13 TicketEvent (Audit Log)
Append-only state machine log preserving complete traceability of all status transitions and operational reasons.

| Field | Type | Required | Allowed Values / Enums | Units / Format | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `event_id` | TEXT | Yes | `EVT-TKT-2026-000001-001`, etc. | `EVT-<ticket>-XXX` | Primary Key | Unique string |
| `ticket_id` | TEXT | Yes | Existing `ticket_id` | Foreign Key | Non-unique | References `Ticket(ticket_id)` |
| `old_status` | TEXT | No | Allowed ticket status or NULL | State enum | Non-unique | NULL for initial creation |
| `new_status` | TEXT | Yes | Allowed ticket status | State enum | Non-unique | Target state |
| `reason` | TEXT | Yes | Explanation of state change | Text string | Non-unique | Non-empty audit explanation |
| `occurred_at` | DATETIME | Yes | ISO 8601 UTC timestamp | `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Valid timestamp |

---

## 3. Deliberate Anomaly Tracking (`issue_type` & Ground Truth)

In accordance with enterprise benchmarking requirements, deliberate negative scenarios are labeled with explicit `issue_type` markers in the database and cataloged in a separate `evaluation/ground_truth.json` / `evaluation/ground_truth.csv` file without corrupting operational features:

| Anomaly Key | Definition | Operational Symptom | Expected Detection |
|---|---|---|---|
| `obsolete_policy_citation` | Answer generated citing a `Retired` policy version rather than the active `Published` version. | `TicketPolicyCitation.version_id` has `status = 'Retired'` | Evaluator flags policy version boundary breach. |
| `sensitive_misrouted` | A workplace harassment or grievance complaint routed to a general queue (`HR-General`) instead of `HR-Confidential`. | `Assignment.assigned_queue = 'HR-General'` with `sensitive_flag = 1` | Evaluator detects confidential containment failure. |
| `sla_calendar_anomaly` | SLA deadline calculated ignoring working calendar (e.g. continuous 24/7 rather than skipping weekend). | `SLA.business_calendar` mismatches working hours calculation | Evaluator identifies SLA calculation anomaly. |
| `unsupported_policy_hallucination` | An inquiry on an ungrounded topic (e.g. pet health insurance or sabbatical) has a fabricated policy answer. | `Resolution.outcome = 'Answered'` without authoritative policy | Evaluator catches hallucination on uncovered topic. |
