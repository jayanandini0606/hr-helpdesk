"""
Response generation service for AI-Powered HR Helpdesk.
Provides deterministic, policy-grounded responses for routine tickets,
safe neutral escalation messages for sensitive cases,
and an optional LLM interface with fallback.
"""

import os
from typing import Dict, Any, List, Optional


def generate_sensitive_escalation_message(
    ticket_id: str,
    queue: str,
    sensitive_types: List[str]
) -> Dict[str, Any]:
    """
    Generates a safe, professional, neutral escalation acknowledgement.
    Guarantees no automatic resolution occurs for sensitive topics.
    """
    type_desc = ", ".join(sensitive_types) if sensitive_types else "confidential employee relations matter"

    message = (
        f"Thank you for reaching out to the HR Helpdesk.\n\n"
        f"Your request involves a matter requiring restricted human review ({type_desc}). "
        f"To ensure your privacy and adhere to company compliance guidelines, this case has "
        f"been routed directly to the authorized **{queue}** team under reference **{ticket_id}**.\n\n"
        f"An authorized HR specialist will review your file and follow up with you through secure, "
        f"confidential channels. No automated decisions or disclosures will be made on this ticket."
    )

    return {
        "message_text": message,
        "message_type": "Escalation",
        "outcome": "Escalated",
        "resolution_summary": f"Escalated to {queue} queue for confidential specialist handling ({type_desc}).",
        "citations": []
    }


def generate_grounded_answer(
    ticket_id: str,
    subject: str,
    description: str,
    retrieved_articles: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generates a deterministic policy-grounded answer citing the retrieved policy
    document, version, and knowledge article.
    """
    if not retrieved_articles:
        message = (
            f"Thank you for contacting the HR Helpdesk regarding '{subject}'.\n\n"
            f"We could not locate an authoritative policy or standard operating procedure that "
            f"directly answers your inquiry. To ensure you receive accurate guidance, your ticket "
            f"has been routed to an HR specialist for manual review.\n\n"
            f"If you have additional context or documentation, please reply to this ticket."
        )
        return {
            "message_text": message,
            "message_type": "Clarification",
            "outcome": "Unresolved",
            "resolution_summary": "No matching authoritative policy version found; routed to HR specialist for clarification.",
            "citations": []
        }

    # Best match
    primary = retrieved_articles[0]

    citations = []
    seen_versions = set()
    for art in retrieved_articles:
        if art["version_id"] not in seen_versions:
            seen_versions.add(art["version_id"])
            citations.append({
                "policy_id": art["policy_id"],
                "policy_title": art["policy_title"],
                "version_id": art["version_id"],
                "version_number": art["version_number"],
                "article_id": art["article_id"],
                "article_title": art["article_title"],
                "snippet": art["snippet"],
            })

    # Grounded response body
    body_lines = [
        f"Hello, thank you for reaching out regarding **{subject}**.\n",
        f"Based on the official published policy **{primary['policy_title']}** (Version {primary['version_number']}):\n",
        f"> {primary['policy_text']}\n",
        f"**Summary Guidance ({primary['article_id']}):**",
        f"{primary['snippet']}\n",
        f"---",
        f"**Applicable Citations:**",
    ]

    for cit in citations:
        body_lines.append(
            f"- **Policy:** {cit['policy_title']} (`{cit['policy_id']}`, Version {cit['version_number']})\n"
            f"  **Article:** {cit['article_title']} (`{cit['article_id']}`)"
        )

    body_lines.append("\nPlease let us know if you require any further assistance.")
    message = "\n".join(body_lines)

    return {
        "message_text": message,
        "message_type": "Answer",
        "outcome": "Answered",
        "resolution_summary": f"Resolved with grounded policy guidance from {primary['policy_title']} (v{primary['version_number']}).",
        "primary_article_id": primary["article_id"],
        "primary_version_id": primary["version_id"],
        "citations": citations
    }


def generate_ticket_response(
    ticket_id: str,
    subject: str,
    description: str,
    classification: Dict[str, Any],
    retrieved_articles: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Central dispatcher for response generation.
    Enforces that sensitive tickets ALWAYS escalate and are never answered automatically.
    """
    if classification.get("sensitive_flag") == 1:
        return generate_sensitive_escalation_message(
            ticket_id=ticket_id,
            queue=classification.get("assigned_queue", "HR-Confidential"),
            sensitive_types=classification.get("sensitive_types", [])
        )

    # Routine request: generate grounded answer
    return generate_grounded_answer(
        ticket_id=ticket_id,
        subject=subject,
        description=description,
        retrieved_articles=retrieved_articles
    )
