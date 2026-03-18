"""Agent 4: polls decision status from DB and escalates if HR does not respond in time."""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from backend.agents.audit_logger import write_audit_log
from backend.config import settings
from backend.db.database import AsyncSessionLocal
from backend.db.models import HiringDecision
from backend.graph.state import HireSignalState
from backend.tools.gmail_tool import send_email


async def run_approval_processor(state: HireSignalState) -> HireSignalState:
    """Wait up to 48 hours for HR approval/rejection updates in the database."""

    state.setdefault("errors", [])
    decision_id = state.get("decision_id")
    if not decision_id:
        state["hr_approved"] = False
        state["hr_rejection_reason"] = "Missing decision ID"
        state["errors"].append("approval_processor: Missing decision_id.")
        return state

    max_polls = 576
    for _ in range(max_polls):
        try:
            async with AsyncSessionLocal() as session:
                decision = (
                    await session.execute(select(HiringDecision).where(HiringDecision.id == decision_id))
                ).scalar_one_or_none()
                if decision is None:
                    raise ValueError(f"Decision {decision_id} not found")

                if decision.status == "APPROVED":
                    state["hr_approved"] = True
                    state["hr_rejection_reason"] = None
                    return state
                if decision.status == "REJECTED":
                    state["hr_approved"] = False
                    state["hr_rejection_reason"] = decision.rejected_reason or "Rejected by HR"
                    return state
        except Exception as exc:
            state["errors"].append(f"approval_processor_poll: {exc}")

        await asyncio.sleep(300)

    state["hr_approved"] = False
    state["hr_rejection_reason"] = "No HR response within 48 hours"

    escalation_subject = f"[HireSignal] Escalation: No HR response for decision {decision_id}"
    escalation_body = (
        "<p>No HR response was received within 48 hours for a hiring recommendation.</p>"
        f"<p>Decision ID: {decision_id}<br>Department: {state.get('department', '')}</p>"
    )
    result = await send_email(settings.escalation_email, escalation_subject, escalation_body)
    if not result.get("success"):
        state["errors"].append(f"approval_processor_escalation_email: {result.get('error')}")
        await write_audit_log(
            agent_name="approval_processor",
            action="Escalation email send failed",
            outcome="ERROR",
            metadata={"run_id": state.get("run_id"), "error": result.get("error")},
        )

    return state
