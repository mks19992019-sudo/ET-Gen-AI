"""Typed shared state definition for the HireSignal LangGraph pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, TypedDict


class HireSignalState(TypedDict):
    """State container passed between all HireSignal agent nodes."""

    # Input
    department: str
    run_id: str
    triggered_by: str

    # Agent 1 output
    workforce_data: dict

    # Agent 2 output
    hiring_decision: dict
    decision_id: Optional[int]

    # Agent 3 output
    notification_sent: bool
    notification_email_id: Optional[str]

    # Agent 4 output
    hr_approved: Optional[bool]
    hr_rejection_reason: Optional[str]

    # Agent 5 output
    jd_text: Optional[str]

    # Agent 6 output
    jd_approved: Optional[bool]

    # Agent 7 output
    linkedin_post_id: Optional[str]
    slack_notified: bool
    calendar_event_id: Optional[str]

    # Shared
    audit_entries: List[dict]
    errors: List[str]
