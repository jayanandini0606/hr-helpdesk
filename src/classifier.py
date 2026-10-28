"""
Classification and sensitive-case routing module for AI-Powered HR Helpdesk.
Classifies employee requests into 5 categories, determines priority,
and detects sensitive cases requiring restricted human handling.
"""

import re
from typing import Dict, Any, List

CATEGORIES_MAP = {
    "CAT-001": {"name": "Benefits", "default_queue": "Benefits", "priority": "Medium"},
    "CAT-002": {"name": "Leave", "default_queue": "Leave", "priority": "Medium"},
    "CAT-003": {"name": "Payroll", "default_queue": "Payroll", "priority": "High"},
    "CAT-004": {"name": "Onboarding", "default_queue": "Onboarding", "priority": "Medium"},
    "CAT-005": {"name": "Employee Relations", "default_queue": "HR-Confidential", "priority": "High"},
}

NAME_TO_CATEGORY_ID = {v["name"].lower(): k for k, v in CATEGORIES_MAP.items()}

# Sensitive case pattern definitions with associated queues and priorities
SENSITIVE_PATTERNS = [
    {
        "type": "Harassment / Discrimination",
        "keywords": [
            r"\bharass(?:ment|ed|ing)?\b",
            r"\bdiscriminat(?:ion|ed|ory|ing)?\b",
            r"\bhostile\s+work\s+environment\b",
            r"\bsexual\s+harassment\b",
            r"\bretaliat(?:ion|ed|ing)?\b",
            r"\bracial\s+bias\b",
            r"\bgender\s+bias\b",
            r"\bbully(?:ing|ied)?\b",
            r"\babuse\b",
            r"\bassault\b",
        ],
        "category_id": "CAT-005",
        "queue": "HR-Confidential",
        "priority": "Critical",
        "reason": "Request contains allegations of workplace harassment, discrimination, or retaliation requiring urgent confidential HR review."
    },
    {
        "type": "Employee Grievance / Formal Complaint",
        "keywords": [
            r"\bgrievance\b",
            r"\bformal\s+complaint\b",
            r"\bunfair\s+treatment\b",
            r"\bwhistleblow(?:er|ing)?\b",
            r"\bmanager\s+misconduct\b",
            r"\bwrongful\s+termination\b",
            r"\bthreatened\s+with\s+firing\b",
        ],
        "category_id": "CAT-005",
        "queue": "HR-Confidential",
        "priority": "High",
        "reason": "Request involves a formal employee grievance or manager conduct issue requiring private mediation."
    },
    {
        "type": "Third-Party Private Information",
        "keywords": [
            r"\b(?:colleague|coworker|peer|another\s+employee|manager|boss)'s?\s+(?:salary|pay|compensation|slip|home\s+address|phone|ssn|pan|medical|record)\b",
            r"\bcheck\s+(?:someone|another\s+employee|my\s+coworker)'s?\s+(?:pay|salary|leave|balance)\b",
            r"\bprivate\s+records?\s+of\b",
        ],
        "category_id": "CAT-005",
        "queue": "HR-Confidential",
        "priority": "High",
        "reason": "Request involves unauthorized access to another employee's confidential personal or compensation records."
    },
    {
        "type": "Payroll Dispute / Salary Discrepancy",
        "keywords": [
            r"\bunexpected\s+deduction\b",
            r"\b(?:salary|payroll|paycheck|pay)\s+(?:deduction|discrepancy|missing|shortage|error|cut|dispute)\b",
            r"\bunderpaid\b",
            r"\bdeducted\s+(?:from\s+my\s+salary|without\s+explanation)\b",
            r"\bpaycheck\s+(?:discrepancy|wrong|incorrect|short|dispute)\b",
            r"\bmissing\s+(?:bonus|reimbursement|allowance|commission|pay)\b",
            r"\bdispute\s+my\s+(?:pay|salary|overtime|compensation)\b",
            r"\bpayroll\s+dispute\b",
        ],
        "category_id": "CAT-003",
        "queue": "Payroll",
        "priority": "High",
        "reason": "Request involves a direct payroll compensation discrepancy or deduction dispute requiring specialist audit."
    },
    {
        "type": "Confidential Employee Records",
        "keywords": [
            r"\bdisciplinary\s+record\b",
            r"\bbackground\s+check\s+dispute\b",
            r"\bmedical\s+(?:leave\s+notes?|diagnosis|confidential\s+document)\b",
            r"\bconfidential\s+investigation\b",
        ],
        "category_id": "CAT-005",
        "queue": "HR-Confidential",
        "priority": "High",
        "reason": "Request references sensitive personnel files, medical documentation, or disciplinary history."
    }
]

# Category keyword scoring for routine requests
CATEGORY_KEYWORDS = {
    "CAT-001": [  # Benefits
        r"\bhealth\s+insurance\b", r"\binsurance\b", r"\bbenefits?\b", r"\bcoverage\b",
        r"\bdependent\b", r"\benrollment\b", r"\bmedical\s+card\b", r"\bhealth\s+plan\b",
        r"\bvision\b", r"\bdental\b", r"\bwellness\b", r"\bqualifying\s+life\s+event\b",
    ],
    "CAT-002": [  # Leave
        r"\bleave\b", r"\bannual\s+leave\b", r"\bsick\s+leave\b", r"\bvacation\b",
        r"\bholiday\b", r"\btime\s+off\b", r"\bbalance\b", r"\bpaternity\b",
        r"\bmaternity\b", r"\babsence\b", r"\bpto\b", r"\bcalendar\b",
    ],
    "CAT-003": [  # Payroll
        r"\bpayslip\b", r"\bsalary\b", r"\bpayroll\b", r"\bpay\s+date\b",
        r"\bbank\s+account\b", r"\bdirect\s+deposit\b", r"\btax\s+withholding\b",
        r"\bcompensation\b", r"\bw2\b", r"\bform\s+16\b", r"\bpay\s+schedule\b",
        r"\bdisburse(?:ment|d)?\b",
    ],
    "CAT-004": [  # Onboarding
        r"\bonboarding\b", r"\bnew\s+hires?\b", r"\bnew\s+employees?\b", r"\borientation\b",
        r"\bequipment\b", r"\blaptop\b", r"\bmonitor\b", r"\baccount\s+provisioning\b",
        r"\bcredentials?\b", r"\bchecklists?\b", r"\bfirst\s+(?:\d+\s+)?days?\b", r"\bwelcome\b",
    ],
    "CAT-005": [  # Employee Relations
        r"\bworkplace\b", r"\bconflict\b", r"\bconcern\b", r"\bethics\b",
        r"\bconduct\b", r"\bpolicy\s+violation\b", r"\brelations\b",
    ]
}


def classify_request(
    subject: str,
    description: str,
    user_category_id: str | None = None
) -> Dict[str, Any]:
    """
    Analyzes ticket subject and description to classify category, detect sensitive
    issues, assign routing queue, and calculate priority.
    """
    text = f"{subject or ''} {description or ''}".strip().lower()

    # Step 1: Detect sensitive patterns first
    detected_sensitivities = []
    highest_priority = None
    sensitive_queue = None
    routing_reason = None
    sensitive_category = None

    for pattern_def in SENSITIVE_PATTERNS:
        for kw_regex in pattern_def["keywords"]:
            if re.search(kw_regex, text, re.IGNORECASE):
                detected_sensitivities.append(pattern_def["type"])
                if highest_priority != "Critical":
                    highest_priority = pattern_def["priority"]
                if not sensitive_queue:
                    sensitive_queue = pattern_def["queue"]
                    routing_reason = pattern_def["reason"]
                    sensitive_category = pattern_def["category_id"]
                break

    if detected_sensitivities:
        return {
            "category_id": sensitive_category or "CAT-005",
            "category_name": CATEGORIES_MAP[sensitive_category or "CAT-005"]["name"],
            "priority": highest_priority or "High",
            "sensitive_flag": 1,
            "assigned_queue": sensitive_queue or "HR-Confidential",
            "routing_reason": routing_reason or "Flagged as sensitive request requiring human HR handling.",
            "sensitive_types": list(set(detected_sensitivities)),
            "auto_resolvable": False,
        }

    # Step 2: Routine request classification
    # If user explicitly selected a valid category, respect it unless strongly overridden
    category_scores = {cat_id: 0 for cat_id in CATEGORIES_MAP}

    for cat_id, patterns in CATEGORY_KEYWORDS.items():
        for pat in patterns:
            matches = len(re.findall(pat, text, re.IGNORECASE))
            if matches > 0:
                category_scores[cat_id] += matches

    if user_category_id and user_category_id in CATEGORIES_MAP:
        # Boost user selection
        category_scores[user_category_id] += 2

    # Find highest scoring category
    best_category_id = max(category_scores, key=category_scores.get)
    max_score = category_scores[best_category_id]

    # If no keywords matched and user selected nothing, default to CAT-001 (Benefits) or general
    if max_score == 0 and not (user_category_id and user_category_id in CATEGORIES_MAP):
        best_category_id = "CAT-001"

    category_info = CATEGORIES_MAP[best_category_id]

    # Priority determination for routine requests
    priority = category_info["priority"]
    if re.search(r"\burgent|immediately|asap|critical|emergency\b", text, re.IGNORECASE):
        priority = "High" if priority == "Medium" else "Critical" if priority == "High" else priority

    return {
        "category_id": best_category_id,
        "category_name": category_info["name"],
        "priority": priority,
        "sensitive_flag": 0,
        "assigned_queue": category_info["default_queue"],
        "routing_reason": f"Routine request classified under {category_info['name']} based on topic match.",
        "sensitive_types": [],
        "auto_resolvable": True,
    }
