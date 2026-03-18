"""APScheduler integration for recurring and manual HireSignal pipeline execution."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from backend.agents.audit_logger import update_agent_run, write_audit_log
from backend.db.database import AsyncSessionLocal
from backend.db.models import AgentRun
from backend.graph.state import HireSignalState
from backend.tools.sql_tools import get_team_names


scheduler = AsyncIOScheduler()
_app_ref: FastAPI | None = None


def _build_initial_state(department: str, run_id: str, triggered_by: str) -> HireSignalState:
    """Create a complete initial state object for a single pipeline invocation."""

    return {
        "department": department,
        "run_id": run_id,
        "triggered_by": triggered_by,
        "workforce_data": {},
        "hiring_decision": {},
        "decision_id": None,
        "notification_sent": False,
        "notification_email_id": None,
        "hr_approved": None,
        "hr_rejection_reason": None,
        "jd_text": None,
        "jd_approved": None,
        "linkedin_post_id": None,
        "slack_notified": False,
        "calendar_event_id": None,
        "audit_entries": [],
        "errors": [],
    }


async def create_agent_run_record(run_id: str, triggered_by: str) -> None:
    """Insert an AgentRun row to track status for dashboard and APIs."""

    async with AsyncSessionLocal() as session:
        session.add(
            AgentRun(
                run_id=run_id,
                started_at=datetime.utcnow(),
                completed_at=None,
                status="RUNNING",
                current_step="QUEUED",
                triggered_by=triggered_by,
            )
        )
        await session.commit()


async def run_pipeline_for_departments(
    app: FastAPI,
    departments: list[str],
    run_id: str,
    triggered_by: str,
) -> None:
    """Run the graph sequentially for provided departments under one run identifier."""

    had_errors = False
    if not departments:
        await update_agent_run(run_id=run_id, current_step="NO_TEAMS", status="COMPLETED", completed=True)
        return

    for department in departments:
        state = _build_initial_state(department=department, run_id=run_id, triggered_by=triggered_by)
        thread_id = f"{run_id}:{department}:{uuid4().hex[:8]}"
        try:
            await app.state.graph.ainvoke(state, config={"configurable": {"thread_id": thread_id}})
        except Exception as exc:
            had_errors = True
            await write_audit_log(
                agent_name="scheduler",
                action="Graph invocation failed",
                outcome="ERROR",
                metadata={"run_id": run_id, "department": department, "error": str(exc)},
            )

    if had_errors:
        await update_agent_run(run_id=run_id, current_step="COMPLETE", status="FAILED", completed=True)
    else:
        await update_agent_run(run_id=run_id, current_step="COMPLETE", status="COMPLETED", completed=True)


async def run_pipeline_for_all_teams() -> None:
    """Scheduled job that runs the graph for each team with SCHEDULER trigger source."""

    if _app_ref is None:
        return

    async with AsyncSessionLocal() as session:
        departments = await get_team_names(session)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    for index, department in enumerate(departments, start=1):
        run_id = f"scheduler-{timestamp}-{index}"
        await create_agent_run_record(run_id=run_id, triggered_by="SCHEDULER")
        await run_pipeline_for_departments(_app_ref, [department], run_id=run_id, triggered_by="SCHEDULER")


def configure_scheduler(app: FastAPI) -> None:
    """Bind scheduler to app context and ensure daily cron job is registered."""

    global _app_ref
    _app_ref = app

    scheduler.add_job(
        run_pipeline_for_all_teams,
        "cron",
        hour=9,
        minute=0,
        id="daily_hiresignal_pipeline",
        replace_existing=True,
    )


def start_scheduler() -> None:
    """Start APScheduler if it is not already running."""

    if not scheduler.running:
        scheduler.start()


def shutdown_scheduler() -> None:
    """Shutdown APScheduler safely on app termination."""

    if scheduler.running:
        scheduler.shutdown(wait=False)
