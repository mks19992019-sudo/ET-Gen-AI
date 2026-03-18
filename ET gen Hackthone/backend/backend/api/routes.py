"""FastAPI REST routes for dashboard data, agent control, hiring flow, and audit logs."""

from __future__ import annotations

from datetime import date, datetime, time
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.linkedin_poster import run_linkedin_poster
from backend.db.database import AsyncSessionLocal, get_session
from backend.db.models import AgentRun, AuditLog, HiringDecision
from backend.scheduler import create_agent_run_record, run_pipeline_for_departments
from backend.tools.sql_tools import (
    get_all_employees,
    get_all_teams_dashboard_data,
    get_flagged_teams,
    get_team_signal_scores,
)


api_router = APIRouter(tags=["api"])


class ApproveDecisionPayload(BaseModel):
    """Request body schema for dashboard-based hiring approval."""

    decision_id: int = Field(..., ge=1)


class RejectDecisionPayload(BaseModel):
    """Request body schema for dashboard-based hiring rejection."""

    decision_id: int = Field(..., ge=1)
    reason: str = Field(..., min_length=2)


async def _trigger_linkedin_post_for_decision(decision_id: int) -> None:
    """Run the LinkedIn posting agent for an already approved JD outside full graph flow."""

    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(select(HiringDecision).where(HiringDecision.id == decision_id))
        ).scalar_one_or_none()
        if row is None or not row.jd_text:
            return

        state = {
            "department": row.department,
            "run_id": f"jd-approve-{decision_id}",
            "triggered_by": "MANUAL",
            "workforce_data": {},
            "hiring_decision": {
                "decision": "HIRE",
                "role_needed": row.role_needed,
                "reason": row.reason,
                "urgency": row.urgency,
            },
            "decision_id": row.id,
            "notification_sent": True,
            "notification_email_id": None,
            "hr_approved": True,
            "hr_rejection_reason": None,
            "jd_text": row.jd_text,
            "jd_approved": True,
            "linkedin_post_id": row.linkedin_post_id,
            "slack_notified": False,
            "calendar_event_id": None,
            "audit_entries": [],
            "errors": [],
        }
        await run_linkedin_poster(state)


@api_router.get("/teams")
async def get_teams(session: AsyncSession = Depends(get_session)) -> list[dict]:
    """Return all teams with computed workload/capacity status for dashboard cards."""

    return await get_all_teams_dashboard_data(session)


@api_router.get("/employees")
async def list_employees(session: AsyncSession = Depends(get_session)) -> list[dict]:
    """Return all employees and their current workforce attributes."""

    return await get_all_employees(session)


@api_router.get("/signals")
async def list_signals(session: AsyncSession = Depends(get_session)) -> list[dict]:
    """Return current team signal scores used by the hiring intelligence engine."""

    return await get_team_signal_scores(session)


@api_router.get("/agent/status")
async def get_agent_status(session: AsyncSession = Depends(get_session)) -> dict:
    """Return status of the most recent pipeline run for dashboard indicator widgets."""

    row = (
        await session.execute(select(AgentRun).order_by(AgentRun.started_at.desc()).limit(1))
    ).scalar_one_or_none()
    if row is None:
        return {"status": "IDLE", "last_run": None, "current_step": None}

    status = "RUNNING" if row.status == "RUNNING" else "COMPLETED"
    return {
        "status": status,
        "last_run": row.started_at.isoformat() if row.started_at else None,
        "current_step": row.current_step,
    }


@api_router.post("/agent/run")
async def run_agent_pipeline(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Trigger manual pipeline runs for all teams currently above any signal threshold."""

    run_id = str(uuid4())
    teams = await get_flagged_teams(session)

    await create_agent_run_record(run_id=run_id, triggered_by="MANUAL")
    background_tasks.add_task(
        run_pipeline_for_departments,
        request.app,
        teams,
        run_id,
        "MANUAL",
    )

    return {"success": True, "run_id": run_id}


@api_router.get("/hiring/decisions")
async def list_hiring_decisions(session: AsyncSession = Depends(get_session)) -> list[dict]:
    """Return all hiring decision rows in reverse chronological order."""

    rows = list(
        (
            await session.execute(select(HiringDecision).order_by(HiringDecision.created_at.desc()))
        ).scalars().all()
    )
    return [
        {
            "id": row.id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "department": row.department,
            "role_needed": row.role_needed,
            "urgency": row.urgency,
            "reason": row.reason,
            "status": row.status,
            "jd_text": row.jd_text,
        }
        for row in rows
    ]


@api_router.post("/hiring/approve")
async def approve_hiring_decision(
    payload: ApproveDecisionPayload,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Approve a hiring decision from dashboard action controls."""

    row = (
        await session.execute(select(HiringDecision).where(HiringDecision.id == payload.decision_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Decision not found")

    row.status = "APPROVED"
    row.approved_by = "HR_DASHBOARD"
    await session.commit()
    return {"success": True}


@api_router.post("/hiring/reject")
async def reject_hiring_decision(
    payload: RejectDecisionPayload,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Reject a hiring decision from dashboard action controls with reason."""

    row = (
        await session.execute(select(HiringDecision).where(HiringDecision.id == payload.decision_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Decision not found")

    row.status = "REJECTED"
    row.rejected_reason = payload.reason
    await session.commit()
    return {"success": True}


@api_router.get("/hiring/approve-link", response_class=HTMLResponse)
async def approve_hiring_link(
    decision_id: int = Query(..., ge=1),
    token: str = Query(..., min_length=8),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Handle email approval link clicks for hiring decisions."""

    row = (
        await session.execute(select(HiringDecision).where(HiringDecision.id == decision_id))
    ).scalar_one_or_none()
    if row is None or row.approval_token != token:
        raise HTTPException(status_code=400, detail="Invalid approval link")

    row.status = "APPROVED"
    row.approved_by = "HR_EMAIL_LINK"
    await session.commit()

    return HTMLResponse("<h3>Approved! You can close this tab.</h3>")


@api_router.get("/hiring/reject-link", response_class=HTMLResponse)
async def reject_hiring_link(
    decision_id: int = Query(..., ge=1),
    token: str = Query(..., min_length=8),
    reason: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Render rejection form or process rejection submitted from email link flow."""

    row = (
        await session.execute(select(HiringDecision).where(HiringDecision.id == decision_id))
    ).scalar_one_or_none()
    if row is None or row.approval_token != token:
        raise HTTPException(status_code=400, detail="Invalid rejection link")

    if reason is None:
        return HTMLResponse(
            """
            <html>
              <body>
                <h3>Reject Hiring Recommendation</h3>
                <form method='get'>
                  <input type='hidden' name='decision_id' value='"""
            + str(decision_id)
            + """'>
                  <input type='hidden' name='token' value='"""
            + token
            + """'>
                  <textarea name='reason' rows='5' cols='60' placeholder='Reason for rejection'></textarea><br><br>
                  <button type='submit'>Submit Rejection</button>
                </form>
              </body>
            </html>
            """
        )

    row.status = "REJECTED"
    row.rejected_reason = reason
    await session.commit()
    return HTMLResponse("<h3>Rejected. Your feedback was recorded.</h3>")


@api_router.get("/jd/{id}")
async def get_jd(id: int, session: AsyncSession = Depends(get_session)) -> dict:
    """Return full job description and metadata for a given hiring decision."""

    row = (
        await session.execute(select(HiringDecision).where(HiringDecision.id == id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Decision not found")

    return {
        "id": row.id,
        "role_needed": row.role_needed,
        "department": row.department,
        "urgency": row.urgency,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "status": row.status,
        "jd_text": row.jd_text,
    }


@api_router.post("/jd/{id}/approve")
async def approve_jd_dashboard(
    id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Approve a generated JD from dashboard controls and allow pipeline progression."""

    row = (
        await session.execute(select(HiringDecision).where(HiringDecision.id == id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Decision not found")

    row.jd_approved = True
    await session.commit()
    background_tasks.add_task(_trigger_linkedin_post_for_decision, id)
    return {"success": True}


@api_router.get("/jd/{id}/approve-link", response_class=HTMLResponse)
async def approve_jd_link(
    id: int,
    background_tasks: BackgroundTasks,
    token: str = Query(..., min_length=8),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Handle JD approval clicks from HR email link."""

    row = (
        await session.execute(select(HiringDecision).where(HiringDecision.id == id))
    ).scalar_one_or_none()
    if row is None or row.approval_token != token:
        raise HTTPException(status_code=400, detail="Invalid JD approval link")

    row.jd_approved = True
    await session.commit()
    background_tasks.add_task(_trigger_linkedin_post_for_decision, id)
    return HTMLResponse("<h3>JD Approved! Job will be posted to LinkedIn shortly.</h3>")


@api_router.get("/audit")
async def list_audit_logs(
    today: bool = Query(default=False),
    agent: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Return audit logs with optional date and agent filters for observability."""

    conditions = []
    if today:
        today_start = datetime.combine(date.today(), time.min)
        today_end = datetime.combine(date.today(), time.max)
        conditions.append(AuditLog.timestamp >= today_start)
        conditions.append(AuditLog.timestamp <= today_end)
    if agent:
        conditions.append(AuditLog.agent_name == agent)

    stmt = select(AuditLog)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(AuditLog.timestamp.desc())

    rows = list((await session.execute(stmt)).scalars().all())
    return [
        {
            "id": row.id,
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            "agent_name": row.agent_name,
            "action": row.action,
            "outcome": row.outcome,
            "metadata": row.metadata_json,
        }
        for row in rows
    ]
