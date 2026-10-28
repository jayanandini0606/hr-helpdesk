
PRAGMA foreign_keys = ON;

-- 1. Departments
CREATE TABLE IF NOT EXISTS Department (
    department_id TEXT PRIMARY KEY,
    department_name TEXT NOT NULL UNIQUE,
    default_queue TEXT NOT NULL
);

-- 2. Employees
CREATE TABLE IF NOT EXISTS Employee (
    employee_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    department_id TEXT NOT NULL,
    manager_id TEXT,
    employment_status TEXT NOT NULL
        CHECK (employment_status IN ('Active', 'Inactive', 'Onboarding')),
    audience TEXT NOT NULL
        CHECK (audience IN ('Employee', 'Manager', 'HR', 'IT')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (department_id) REFERENCES Department(department_id),
    FOREIGN KEY (manager_id) REFERENCES Employee(employee_id),
    CHECK (manager_id IS NULL OR manager_id <> employee_id)
);

-- 3. Categories
CREATE TABLE IF NOT EXISTS Category (
    category_id TEXT PRIMARY KEY,
    category_name TEXT NOT NULL UNIQUE,
    default_queue TEXT NOT NULL,
    priority TEXT NOT NULL
        CHECK (priority IN ('Low', 'Medium', 'High', 'Critical'))
);

-- 4. Policy documents
CREATE TABLE IF NOT EXISTS PolicyDocument (
    policy_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category_id TEXT NOT NULL,
    owner_department_id TEXT NOT NULL,
    audience TEXT NOT NULL
        CHECK (audience IN ('Employee', 'Manager', 'HR', 'All')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (category_id) REFERENCES Category(category_id),
    FOREIGN KEY (owner_department_id)
        REFERENCES Department(department_id)
);

-- 5. Policy versions
CREATE TABLE IF NOT EXISTS PolicyVersion (
    version_id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    policy_text TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('Draft', 'Published', 'Retired')),
    created_at TEXT NOT NULL,
    UNIQUE (policy_id, version_number),
    FOREIGN KEY (policy_id) REFERENCES PolicyDocument(policy_id),
    CHECK (
        effective_to IS NULL OR effective_to >= effective_from
    )
);

-- 6. Knowledge articles
CREATE TABLE IF NOT EXISTS KnowledgeArticle (
    article_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    snippet TEXT NOT NULL,
    category_id TEXT NOT NULL,
    version_id TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('Draft', 'Published', 'Archived')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (category_id) REFERENCES Category(category_id),
    FOREIGN KEY (version_id) REFERENCES PolicyVersion(version_id)
);

-- 7. Tickets
CREATE TABLE IF NOT EXISTS Ticket (
    ticket_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL,
    category_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Open'
        CHECK (status IN (
            'Open', 'Awaiting_Employee', 'In_Progress',
            'Resolved', 'Closed'
        )),
    priority TEXT NOT NULL
        CHECK (priority IN ('Low', 'Medium', 'High', 'Critical')),
    sensitive_flag INTEGER NOT NULL DEFAULT 0
        CHECK (sensitive_flag IN (0, 1)),
    issue_type TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (employee_id) REFERENCES Employee(employee_id),
    FOREIGN KEY (category_id) REFERENCES Category(category_id),
    CHECK (updated_at >= created_at)
);

-- 8. Messages
CREATE TABLE IF NOT EXISTS Message (
    message_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL,
    sequence_number INTEGER NOT NULL CHECK (sequence_number > 0),
    sender_type TEXT NOT NULL
        CHECK (sender_type IN ('Employee', 'Assistant', 'HR', 'System')),
    message_text TEXT NOT NULL,
    message_type TEXT NOT NULL
        CHECK (message_type IN (
            'Request', 'Clarification', 'Answer',
            'Escalation', 'Resolution'
        )),
    created_at TEXT NOT NULL,
    UNIQUE (ticket_id, sequence_number),
    FOREIGN KEY (ticket_id) REFERENCES Ticket(ticket_id)
);

-- 9. Assignment history
CREATE TABLE IF NOT EXISTS Assignment (
    assignment_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL,
    assigned_queue TEXT NOT NULL,
    assigned_to TEXT,
    reason TEXT NOT NULL,
    assigned_at TEXT NOT NULL,
    ended_at TEXT,
    FOREIGN KEY (ticket_id) REFERENCES Ticket(ticket_id),
    CHECK (ended_at IS NULL OR ended_at >= assigned_at)
);

-- 10. SLA records
CREATE TABLE IF NOT EXISTS SLA (
    sla_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL UNIQUE,
    policy_name TEXT NOT NULL,
    response_due_at TEXT NOT NULL,
    resolution_due_at TEXT NOT NULL,
    business_calendar TEXT NOT NULL,
    response_met INTEGER CHECK (response_met IN (0, 1)),
    resolution_met INTEGER CHECK (resolution_met IN (0, 1)),
    FOREIGN KEY (ticket_id) REFERENCES Ticket(ticket_id),
    CHECK (resolution_due_at >= response_due_at)
);

-- 11. Resolutions
CREATE TABLE IF NOT EXISTS Resolution (
    resolution_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL UNIQUE,
    outcome TEXT NOT NULL
        CHECK (outcome IN (
            'Answered', 'Escalated', 'Rejected', 'Unresolved'
        )),
    resolution_summary TEXT NOT NULL,
    resolved_at TEXT,
    article_id TEXT,
    version_id TEXT,
    FOREIGN KEY (ticket_id) REFERENCES Ticket(ticket_id),
    FOREIGN KEY (article_id) REFERENCES KnowledgeArticle(article_id),
    FOREIGN KEY (version_id) REFERENCES PolicyVersion(version_id)
);

-- 12. Bridge table: which policy versions supported which tickets?
CREATE TABLE IF NOT EXISTS TicketPolicyCitation (
    ticket_id TEXT NOT NULL,
    version_id TEXT NOT NULL,
    article_id TEXT,
    cited_at TEXT NOT NULL,
    PRIMARY KEY (ticket_id, version_id),
    FOREIGN KEY (ticket_id) REFERENCES Ticket(ticket_id),
    FOREIGN KEY (version_id) REFERENCES PolicyVersion(version_id),
    FOREIGN KEY (article_id) REFERENCES KnowledgeArticle(article_id)
);

-- 13. Append-only ticket state history
CREATE TABLE IF NOT EXISTS TicketEvent (
    event_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (ticket_id) REFERENCES Ticket(ticket_id)
);

-- Useful indexes for common lookups
CREATE INDEX IF NOT EXISTS idx_ticket_status ON Ticket(status);
CREATE INDEX IF NOT EXISTS idx_ticket_category ON Ticket(category_id);
CREATE INDEX IF NOT EXISTS idx_message_ticket ON Message(ticket_id);
CREATE INDEX IF NOT EXISTS idx_assignment_ticket ON Assignment(ticket_id);
CREATE INDEX IF NOT EXISTS idx_policy_effective_dates
    ON PolicyVersion(policy_id, effective_from, effective_to);
