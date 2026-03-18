"""Agent 7: posts approved jobs to LinkedIn and notifies Slack/Calendar in parallel."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select

from backend.agents.audit_logger import write_audit_log
from backend.db.database import AsyncSessionLocal
from backend.db.models import HiringDecision
from backend.graph.state import HireSignalState
from backend.tools.calendar_tool import create_calendar_event
from backend.tools.linkedin_tool import post_linkedin_job
from backend.tools.slack_tool import send_slack_message


async def _post_linkedin(state: HireSignalState) -> dict[str, Any]:
    """Execute LinkedIn posting API call for the approved role."""

    decision = state.get("hiring_decision", {})
    return await post_linkedin_job(
        role_needed=str(decision.get("role_needed", "Unknown Role")),
        department=state.get("department", ""),
        jd_text=str(state.get("jd_text", "")),
    )


async def _send_slack(state: HireSignalState, post_url: str) -> dict[str, Any]:
    """Send Slack notification for a newly posted role."""

    decision = state.get("hiring_decision", {})
    message = (
        f"New job posted! {decision.get('role_needed', 'Unknown Role')} in "
        f"{state.get('department', '')}. LinkedIn: {post_url or 'N/A'}"
    )
    return await send_slack_message(message)


async def _send_slack_after_linkedin(
    state: HireSignalState,
    linkedin_task: "asyncio.Task[dict[str, Any]]",
) -> dict[str, Any]:
    """Wait for LinkedIn outcome and then post Slack notification with resulting URL."""

    linkedin_result = await linkedin_task
    return await _send_slack(state, str(linkedin_result.get("post_url", "")))


async def _create_calendar(state: HireSignalState) -> dict[str, Any]:
    """Reserve interview slots in calendar one week ahead for the role."""

    decision = state.get("hiring_decision", {})
    role_needed = str(decision.get("role_needed", "Unknown Role"))

    start_dt = (datetime.utcnow() + timedelta(days=7)).replace(hour=10, minute=0, second=0, microsecond=0)
    end_dt = (datetime.utcnow() + timedelta(days=7)).replace(hour=17, minute=0, second=0, microsecond=0)

    return await create_calendar_event(
        title=f"Interview Slots - {role_needed}",
        start_iso=start_dt.isoformat(),
        end_iso=end_dt.isoformat(),
        description=f"Reserved for {role_needed} interviews",
    )


async def run_linkedin_poster(state: HireSignalState) -> HireSignalState:
    """Execute LinkedIn, Slack, and Calendar actions concurrently and persist outcomes."""

    state.setdefault("errors", [])
    if state.get("jd_approved") is not True:
        return state

    linkedin_task = asyncio.create_task(_post_linkedin(state))
    calendar_task = asyncio.create_task(_create_calendar(state))
    slack_task = asyncio.create_task(_send_slack_after_linkedin(state, linkedin_task))
    linkedin_result, slack_result, calendar_result = await asyncio.gather(
        linkedin_task,
        slack_task,
        calendar_task,
    )

    if linkedin_result.get("success"):
        state["linkedin_post_id"] = linkedin_result.get("post_id") or None
    else:
        state["linkedin_post_id"] = None
        state["errors"].append(f"linkedin_poster_linkedin: {linkedin_result.get('error')}")
        await write_audit_log(
            agent_name="linkedin_poster",
            action="LinkedIn posting failed",
            outcome="ERROR",
            metadata={"run_id": state.get("run_id"), "error": linkedin_result.get("error")},
        )

    state["slack_notified"] = bool(slack_result.get("success"))
    if not slack_result.get("success"):
        state["errors"].append(f"linkedin_poster_slack: {slack_result.get('error')}")
        await write_audit_log(
            agent_name="linkedin_poster",
            action="Slack notification failed",
            outcome="ERROR",
            metadata={"run_id": state.get("run_id"), "error": slack_result.get("error")},
        )

    if calendar_result.get("success"):
        state["calendar_event_id"] = calendar_result.get("event_id") or None
    else:
        state["calendar_event_id"] = None
        state["errors"].append(f"linkedin_poster_calendar: {calendar_result.get('error')}")
        await write_audit_log(
            agent_name="linkedin_poster",
            action="Calendar event creation failed",
            outcome="ERROR",
            metadata={"run_id": state.get("run_id"), "error": calendar_result.get("error")},
        )

    decision_id = state.get("decision_id")
    if decision_id:
        try:
            async with AsyncSessionLocal() as session:
                row = (
                    await session.execute(select(HiringDecision).where(HiringDecision.id == decision_id))
                ).scalar_one_or_none()
                if row:
                    row.linkedin_post_id = state.get("linkedin_post_id")
                    if state.get("linkedin_post_id"):
                        row.status = "POSTED"
                    await session.commit()
        except Exception as exc:
            state["errors"].append(f"linkedin_poster_db: {exc}")
            await write_audit_log(
                agent_name="linkedin_poster",
                action="Failed to persist posting outcomes",
                outcome="ERROR",
                metadata={"run_id": state.get("run_id"), "error": str(exc)},
            )

    return state
