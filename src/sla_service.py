"""
SLA management service for AI-Powered HR Helpdesk.
Calculates response and resolution deadlines based on ticket priority and working calendar,
tracks SLA compliance status (met / breached / pending), and calculates ticket age.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

# Default SLA targets in hours
SLA_TARGETS_HOURS = {
    "Critical": {"response": 1, "resolution": 4},
    "High": {"response": 4, "resolution": 24},
    "Medium": {"response": 8, "resolution": 48},
    "Low": {"response": 24, "resolution": 72},
}

DEFAULT_CALENDAR = "Standard Business Hours (09:00-17:00 Mon-Fri)"


def parse_iso_datetime(dt_str: str) -> datetime:
    """Parses an ISO format datetime string into UTC datetime object."""
    dt_str = dt_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def format_iso_datetime(dt: datetime) -> str:
    """Formats a datetime object as UTC ISO string."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def add_business_hours(start_dt: datetime, hours: float) -> datetime:
    """
    Adds `hours` of working time to `start_dt`.
    Working calendar: Monday to Friday, 09:00 to 17:00 (8 hours/day).
    Non-business hours and weekends are rolled forward to the next business day 09:00.
    """
    current = start_dt.astimezone(timezone.utc)
    remaining_minutes = int(hours * 60)

    # Roll to valid business start if starting outside business hours or on weekend
    while True:
        # Weekend check (5 = Saturday, 6 = Sunday)
        if current.weekday() >= 5:
            # Advance to next Monday 09:00
            days_to_add = 7 - current.weekday()
            current = current.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=days_to_add)
            continue

        # Before work hours (< 09:00)
        if current.hour < 9:
            current = current.replace(hour=9, minute=0, second=0, microsecond=0)
            break

        # After work hours (>= 17:00)
        if current.hour >= 17:
            # Advance to next day 09:00
            current = (current + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            continue

        break

    # Now step through business minutes
    while remaining_minutes > 0:
        if current.weekday() >= 5:
            days_to_add = 7 - current.weekday()
            current = current.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=days_to_add)
            continue

        end_of_day = current.replace(hour=17, minute=0, second=0, microsecond=0)
        available_minutes_today = int((end_of_day - current).total_seconds() / 60)

        if remaining_minutes <= available_minutes_today:
            current = current + timedelta(minutes=remaining_minutes)
            remaining_minutes = 0
        else:
            remaining_minutes -= available_minutes_today
            # Advance to next day 09:00
            current = (current + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

    return current


def calculate_sla_deadlines(
    priority: str,
    created_at_iso: str,
    calendar: str = DEFAULT_CALENDAR
) -> Dict[str, str]:
    """
    Calculates response_due_at and resolution_due_at according to priority and calendar.
    """
    targets = SLA_TARGETS_HOURS.get(priority, SLA_TARGETS_HOURS["Medium"])
    created_dt = parse_iso_datetime(created_at_iso)

    if "24x7" in calendar.lower():
        response_dt = created_dt + timedelta(hours=targets["response"])
        resolution_dt = created_dt + timedelta(hours=targets["resolution"])
    else:
        response_dt = add_business_hours(created_dt, targets["response"])
        resolution_dt = add_business_hours(created_dt, targets["resolution"])

    return {
        "policy_name": f"{priority}-Priority Standard SLA",
        "response_due_at": format_iso_datetime(response_dt),
        "resolution_due_at": format_iso_datetime(resolution_dt),
        "business_calendar": calendar,
    }


def evaluate_sla_status(
    sla_row: Dict[str, Any],
    first_response_time_iso: Optional[str] = None,
    resolved_time_iso: Optional[str] = None,
    current_time_iso: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates current SLA compliance state for display and tracking.
    """
    now_dt = parse_iso_datetime(current_time_iso) if current_time_iso else datetime.now(timezone.utc)
    resp_due_dt = parse_iso_datetime(sla_row["response_due_at"])
    res_due_dt = parse_iso_datetime(sla_row["resolution_due_at"])

    # Response check
    if first_response_time_iso:
        resp_actual_dt = parse_iso_datetime(first_response_time_iso)
        response_met = 1 if resp_actual_dt <= resp_due_dt else 0
        response_overdue = False
    else:
        response_met = sla_row.get("response_met")
        response_overdue = now_dt > resp_due_dt if response_met is None else False

    # Resolution check
    if resolved_time_iso:
        res_actual_dt = parse_iso_datetime(resolved_time_iso)
        resolution_met = 1 if res_actual_dt <= res_due_dt else 0
        resolution_overdue = False
    else:
        resolution_met = sla_row.get("resolution_met")
        resolution_overdue = now_dt > res_due_dt if resolution_met is None else False

    return {
        "response_met": response_met,
        "resolution_met": resolution_met,
        "is_response_overdue": response_overdue,
        "is_resolution_overdue": resolution_overdue,
        "response_due_at": sla_row["response_due_at"],
        "resolution_due_at": sla_row["resolution_due_at"],
    }


def format_ticket_age(created_at_iso: str, end_time_iso: Optional[str] = None) -> str:
    """Calculates human-readable age of a ticket."""
    start_dt = parse_iso_datetime(created_at_iso)
    end_dt = parse_iso_datetime(end_time_iso) if end_time_iso else datetime.now(timezone.utc)
    diff = max(timedelta(0), end_dt - start_dt)

    total_seconds = int(diff.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60

    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
