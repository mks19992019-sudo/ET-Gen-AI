"""Agent 3: sends hiring recommendation emails with approve/reject links to HR."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from backend.agents.audit_logger import write_audit_log
from backend.config import settings
from backend.db.database import AsyncSessionLocal
from backend.db.models import HiringDecision
from backend.graph.state import HireSignalState
from backend.tools.gmail_tool import send_email


def _build_hr_email_body(
    role_needed: str,
    department: str,
    urgency: str,
    reason: str,
    decision_id: int,
    token: str,
) -> str:
    """Create HTML body for HR recommendation notification."""

    approve_link = f"{settings.base_url}/api/hiring/approve-link?decision_id={decision_id}&token={token}"
    reject_link = f"{settings.base_url}/api/hiring/reject-link?decision_id={decision_id}&token={token}"
    return (
        "<p>HireSignal has detected a hiring need.</p>"
        f"<p><b>Role:</b> {role_needed}<br>"
        f"<b>Department:</b> {department}<br>"
        f"<b>Urgency:</b> {urgency}<br>"
        f"<b>Reason:</b> {reason}</p>"
        f"<p>To approve: <a href=\"{approve_link}\">Click here</a></p>"
        f"<p>To reject: <a href=\"{reject_link}\">Click here</a></p>"
        "<p>This recommendation was generated automatically by HireSignal.</p>"
    )


async def run_hr_notifier(state: HireSignalState) -> HireSignalState:
    """Send an HR email for HIRE decisions and persist approval token state."""

    state.setdefault("errors", [])
    decision = state.get("hiring_decision", {})
    if str(decision.get("decision", "")).upper() != "HIRE":
        state["notification_sent"] = False
        state["notification_email_id"] = None
        return state

    decision_id = state.get("decision_id")
    if not decision_id:
        state["notification_sent"] = False
        state["notification_email_id"] = None
        state["errors"].append("hr_notifier: Missing decision_id.")
        return state

    token = str(uuid4())
    role_needed = str(decision.get("role_needed", "Unknown Role"))
    urgency = str(decision.get("urgency", "LOW"))
    reason = str(decision.get("reason", "No rationale provided."))

    try:
        async with AsyncSessionLocal() as session:
            row = (await session.execute(select(HiringDecision).where(HiringDecision.id == decision_id))).scalar_one_or_none()
            if row is None:
                raise ValueError(f"HiringDecision {decision_id} not found.")
            row.approval_token = token
            await session.commit()
    except Exception as exc:
        state["notification_sent"] = False
        state["notification_email_id"] = None
        state["errors"].append(f"hr_notifier_db: {exc}")
        await write_audit_log(
            agent_name="hr_notifier",
            action="Failed to persist approval token",
            outcome="ERROR",
            metadata={"run_id": state.get("run_id"), "error": str(exc)},
        )
        return state

    subject = f"[HireSignal] Hiring Recommendation - {role_needed} ({urgency} Priority)"
    body = _build_hr_email_body(
        role_needed=role_needed,
        department=state.get("department", ""),
        urgency=urgency,
        reason=reason,
        decision_id=decision_id,
        token=token,
    )

    result = await send_email(settings.hr_email, subject, body)
    if result.get("success"):
        state["notification_sent"] = True
        state["notification_email_id"] = result.get("email_id") or None
    else:
        state["notification_sent"] = False
        state["notification_email_id"] = None
        state["errors"].append(f"hr_notifier_email: {result.get('error')}")
        await write_audit_log(
            agent_name="hr_notifier",
            action="Gmail notification send failed",
            outcome="ERROR",
            metadata={"run_id": state.get("run_id"), "error": result.get("error")},
        )

    return state
