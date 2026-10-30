"""
Policy and knowledge retrieval module for AI-Powered HR Helpdesk.
Retrieves relevant knowledge articles and resolves currently applicable
published policy versions based on effective dates and ticket submission time.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
import re
from src.database import query_all, query_one

STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "with", "from", "that", "this",
    "can", "how", "what", "where", "when", "why", "who", "which", "are",
    "is", "was", "were", "be", "been", "have", "has", "had", "take", "need",
    "want", "please", "would", "like", "about", "does", "do", "did", "will",
    "our", "their", "your", "my", "any", "all", "out", "get", "under", "into",
    "over", "after", "per", "during"
}

# Unsupported/uncovered policy topics in this organization
UNSUPPORTED_PATTERNS = [
    r"\bsabbatical\b",
    r"\bpet\s+insurance\b",
    r"\bveterinary\b",
    r"\bpet\s+medicine\b",
    r"\btuition\s+reimbursement\b",
    r"\bgym\s+membership\b",
    r"\bfitness\s+stipend\b",
    r"\brelocation\s+allowance\b",
]


def is_unsupported_topic(text: str) -> bool:
    """Detects whether a request is inquiring about a topic with no company policy."""
    for pat in UNSUPPORTED_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def get_current_iso_time() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_current_iso_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def find_applicable_policy_version(
    policy_id: str,
    as_of_date: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """
    Finds the active published policy version effective at `as_of_date`.
    Does NOT simply take MAX(version_number) — verifies status='Published'
    and effective_from <= as_of_date <= effective_to.
    """
    target_date = as_of_date or get_current_iso_date()

    sql = """
        SELECT pv.version_id, pv.policy_id, pv.version_number,
               pv.effective_from, pv.effective_to, pv.policy_text,
               pv.status, pd.title as policy_title, pd.category_id,
               pd.owner_department_id, pd.audience
        FROM PolicyVersion pv
        JOIN PolicyDocument pd ON pv.policy_id = pd.policy_id
        WHERE pv.policy_id = ?
          AND pv.status = 'Published'
          AND pv.effective_from <= ?
          AND (pv.effective_to IS NULL OR pv.effective_to >= ?)
        ORDER BY pv.version_number DESC
        LIMIT 1
    """
    return query_one(sql, (policy_id, target_date, target_date), db_path=db_path)


def retrieve_relevant_knowledge(
    query_text: str,
    category_id: Optional[str] = None,
    as_of_date: Optional[str] = None,
    limit: int = 3,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves knowledge articles relevant to query_text, joined with their
    underlying published policy versions and documents.
    Enforces that only Published articles linked to currently applicable Published
    policy versions are returned.
    """
    # Check for known unsupported policies first
    if is_unsupported_topic(query_text):
        return []

    target_date = as_of_date or get_current_iso_date()

    # Extract non-stopword alphanumeric tokens
    all_words = re.findall(r"\b[a-zA-Z0-9]{3,}\b", query_text.lower())
    tokens = [t for t in all_words if t not in STOPWORDS]
    if not tokens:
        tokens = all_words

    if not tokens:
        return []

    params = [target_date, target_date]
    cat_filter = ""
    if category_id:
        cat_filter = "AND ka.category_id = ?"
        params.append(category_id)

    # Fetch published articles and applicable published policy versions
    sql = f"""
        SELECT ka.article_id, ka.title as article_title, ka.snippet,
               ka.category_id, ka.version_id, ka.status as article_status,
               pv.policy_id, pv.version_number, pv.effective_from,
               pv.effective_to, pv.policy_text, pv.status as version_status,
               pd.title as policy_title
        FROM KnowledgeArticle ka
        JOIN PolicyVersion pv ON ka.version_id = pv.version_id
        JOIN PolicyDocument pd ON pv.policy_id = pd.policy_id
        WHERE ka.status = 'Published'
          AND pv.status = 'Published'
          AND pv.effective_from <= ?
          AND (pv.effective_to IS NULL OR pv.effective_to >= ?)
          {cat_filter}
    """

    candidates = query_all(sql, tuple(params), db_path=db_path)
    if not candidates and category_id:
        # Fallback search across all categories if none found in specific category
        sql_fallback = """
            SELECT ka.article_id, ka.title as article_title, ka.snippet,
                   ka.category_id, ka.version_id, ka.status as article_status,
                   pv.policy_id, pv.version_number, pv.effective_from,
                   pv.effective_to, pv.policy_text, pv.status as version_status,
                   pd.title as policy_title
            FROM KnowledgeArticle ka
            JOIN PolicyVersion pv ON ka.version_id = pv.version_id
            JOIN PolicyDocument pd ON pv.policy_id = pd.policy_id
            WHERE ka.status = 'Published'
              AND pv.status = 'Published'
              AND pv.effective_from <= ?
              AND (pv.effective_to IS NULL OR pv.effective_to >= ?)
        """
        candidates = query_all(sql_fallback, (target_date, target_date), db_path=db_path)

    scored_by_policy: Dict[str, Dict[str, Any]] = {}

    for cand in candidates:
        text_corpus = f"{cand['article_title']} {cand['snippet']} {cand['policy_title']} {cand['policy_text']}".lower()
        title_corpus = f"{cand['policy_title']} {cand['article_title']}".lower()

        score = 0
        matched_tokens = []

        for token in tokens:
            if token in text_corpus:
                score += 2
                matched_tokens.append(token)
                # Strong bonus for matching title keywords
                if token in title_corpus:
                    score += 5

        # Phrase matches
        for sub_len in [3, 2]:
            for i in range(len(tokens) - sub_len + 1):
                phrase = " ".join(tokens[i:i + sub_len])
                if phrase in text_corpus:
                    score += 6
                if phrase in title_corpus:
                    score += 10

        if score >= 3:
            cand_copy = dict(cand)
            cand_copy["score"] = score
            cand_copy["matched_tokens"] = matched_tokens

            pol_id = cand["policy_id"]
            # Deduplicate by policy_id keeping highest scoring article
            if pol_id not in scored_by_policy or score > scored_by_policy[pol_id]["score"]:
                scored_by_policy[pol_id] = cand_copy

    scored_results = list(scored_by_policy.values())
    # Sort descending by score
    scored_results.sort(key=lambda x: x["score"], reverse=True)
    return scored_results[:limit]


def get_all_policies_summary(
    as_of_date: Optional[str] = None,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves all policy documents with their versions, linked articles,
    and flags which version is currently active based on as_of_date.
    """
    target_date = as_of_date or get_current_iso_date()

    policies = query_all("""
        SELECT pd.*, c.category_name, d.department_name
        FROM PolicyDocument pd
        JOIN Category c ON pd.category_id = c.category_id
        JOIN Department d ON pd.owner_department_id = d.department_id
        ORDER BY pd.policy_id ASC
    """, db_path=db_path)

    for pol in policies:
        policy_id = pol["policy_id"]
        versions = query_all("""
            SELECT * FROM PolicyVersion
            WHERE policy_id = ?
            ORDER BY version_number ASC
        """, (policy_id,), db_path=db_path)

        for v in versions:
            # Check if this version is currently active
            is_active = (
                v["status"] == "Published" and
                v["effective_from"] <= target_date and
                (v["effective_to"] is None or v["effective_to"] >= target_date)
            )
            v["is_active"] = is_active

            # Fetch linked articles
            articles = query_all("""
                SELECT article_id, title, snippet, status FROM KnowledgeArticle
                WHERE version_id = ?
                ORDER BY article_id ASC
            """, (v["version_id"],), db_path=db_path)
            v["articles"] = articles

        pol["versions"] = versions

    return policies
