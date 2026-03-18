"""Agent 6: sends generated JD to HR and waits for approval signal in database."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy import select

from backend.agents.audit_logger import write_audit_log
from backend.config import settings
from backend.db.database import AsyncSessionLocal
from backend.db.models import HiringDecision
from backend.graph.state import HireSignalState
from backend.tools.gmail_tool import send_email


def _build_jd_review_email(role_needed: str, decision_id: int, token: str, jd_text: str) -> str:
    """Build the HTML review email body containing JD and approval links."""

    approve_link = f"{settings.base_url}/api/jd/{decision_id}/approve-link?token={token}"
    return (
        f"<p>Please review the generated Job Description for <b>{role_needed}</b>.</p>"
        f"<pre style=\"white-space: pre-wrap; font-family: Arial, sans-serif;\">{jd_text}</pre>"
        f"<p>Approve: <a href=\"{approve_link}\">Approve JD</a></p>"
        "<p>For edits, reply to this email with comments.</p>"
    )


async def run_jd_reviewer(state: HireSignalState) -> HireSignalState:
    """Send JD to HR and poll DB up to 24 hours for JD approval."""

    state.setdefault("errors", [])
    decision_id = state.get("decision_id")
    jd_text = state.get("jd_text")
    if not decision_id or not jd_text:
        state["jd_approved"] = False
        if not decision_id:
            state["errors"].append("jd_reviewer: Missing decision_id.")
        if not jd_text:
            state["errors"].append("jd_reviewer: Missing jd_text.")
        return state

    token = str(uuid4())
    try:
        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(select(HiringDecision).where(HiringDecision.id == decision_id))
            ).scalar_one_or_none()
            if row is None:
                raise ValueError(f"Decision {decision_id} not found")
            row.approval_token = token
            row.jd_approved = False
            await session.commit()
    except Exception as exc:
        state["errors"].append(f"jd_reviewer_db_token: {exc}")
        await write_audit_log(
            agent_name="jd_reviewer",
            action="Failed to store JD approval token",
            outcome="ERROR",
            metadata={"run_id": state.get("run_id"), "error": str(exc)},
        )
        state["jd_approved"] = False
        return state

    decision = state.get("hiring_decision", {})
    role_needed = str(decision.get("role_needed", "Unknown Role"))
    subject = f"[HireSignal] Please Review Job Description - {role_needed}"
    email_body = _build_jd_review_email(role_needed, decision_id, token, jd_text)

    send_result = await send_email(settings.hr_email, subject, email_body)
    if not send_result.get("success"):
        state["errors"].append(f"jd_reviewer_email: {send_result.get('error')}")
        await write_audit_log(
            agent_name="jd_reviewer",
            action="JD review email send failed",
            outcome="ERROR",
            metadata={"run_id": state.get("run_id"), "error": send_result.get("error")},
        )

    max_polls = 288
    for _ in range(max_polls):
        try:
            async with AsyncSessionLocal() as session:
                row = (
                    await session.execute(select(HiringDecision).where(HiringDecision.id == decision_id))
                ).scalar_one_or_none()
                if row and row.jd_approved:
                    state["jd_approved"] = True
                    return state
        except Exception as exc:
            state["errors"].append(f"jd_reviewer_poll: {exc}")

        await asyncio.sleep(300)

    state["jd_approved"] = False
    state["jd_retry_count"] = state.get("jd_retry_count", 0) + 1
    state["errors"].append("jd_reviewer: JD approval timeout after 24 hours.")
    return state
