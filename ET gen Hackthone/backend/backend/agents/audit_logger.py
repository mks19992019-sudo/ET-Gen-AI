"""Final audit agent plus shared audit/run-tracking helpers for all pipeline nodes."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from langsmith import Client
from sqlalchemy import select

from backend.api.websocket import manager
from backend.config import settings
from backend.db.database import AsyncSessionLocal
from backend.db.models import AgentRun, AuditLog
from backend.graph.state import HireSignalState


async def write_audit_log(
    agent_name: str,
    action: str,
    outcome: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Persist one structured audit record to the database."""

    try:
        async with AsyncSessionLocal() as session:
            session.add(
                AuditLog(
                    timestamp=datetime.utcnow(),
                    agent_name=agent_name,
                    action=action,
                    outcome=outcome,
                    metadata_json=metadata,
                )
            )
            await session.commit()
    except Exception:
        # Never allow audit logging failures to break the pipeline.
        return


async def broadcast_event(
    agent_name: str,
    action: str,
    status: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Broadcast one live event to connected WebSocket clients."""

    payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "agent": agent_name,
        "action": action,
        "status": status,
    }
    if extra:
        payload.update(extra)
    await manager.broadcast(payload)


async def append_state_audit(
    state: HireSignalState,
    agent_name: str,
    action: str,
    outcome: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append a normalized audit entry to in-memory graph state."""

    state.setdefault("audit_entries", [])
    state["audit_entries"].append(
        {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_name": agent_name,
            "action": action,
            "outcome": outcome,
            "metadata": metadata or {},
        }
    )


async def update_agent_run(
    run_id: str,
    current_step: str | None = None,
    status: str | None = None,
    completed: bool = False,
) -> None:
    """Update run progress/status fields for dashboard visibility."""

    try:
        async with AsyncSessionLocal() as session:
            row = (await session.execute(select(AgentRun).where(AgentRun.run_id == run_id))).scalar_one_or_none()
            if row is None:
                return
            if current_step is not None:
                row.current_step = current_step
            if status is not None:
                row.status = status
            if completed:
                row.completed_at = datetime.utcnow()
            await session.commit()
    except Exception:
        return


def build_pipeline_summary(state: HireSignalState) -> dict[str, Any]:
    """Build a compact completion summary for broadcast payloads."""

    return {
        "department": state.get("department"),
        "decision": state.get("hiring_decision", {}).get("decision"),
        "decision_id": state.get("decision_id"),
        "hr_approved": state.get("hr_approved"),
        "jd_approved": state.get("jd_approved"),
        "linkedin_post_id": state.get("linkedin_post_id"),
        "errors_count": len(state.get("errors", [])),
    }


async def flush_langsmith_traces() -> None:
    """Best-effort LangSmith flush so traces are available immediately after completion."""

    if not settings.langsmith_api_key:
        return
    try:
        client = Client(api_key=settings.langsmith_api_key)
        if hasattr(client, "flush"):
            await asyncio.to_thread(client.flush)
    except Exception:
        return


async def run_audit_logger(state: HireSignalState) -> HireSignalState:
    """Finalize run status, write terminal audit logs, and emit completion broadcast."""

    run_id = state.get("run_id", "")
    summary = build_pipeline_summary(state)
    final_status = "FAILED" if state.get("errors") else "COMPLETED"

    await write_audit_log(
        agent_name="audit_logger",
        action="Pipeline finished",
        outcome="SUCCESS" if final_status == "COMPLETED" else "WARNING",
        metadata={"run_id": run_id, "summary": summary},
    )
    await append_state_audit(
        state,
        agent_name="audit_logger",
        action="Pipeline finished",
        outcome="SUCCESS" if final_status == "COMPLETED" else "WARNING",
        metadata={"run_id": run_id, "summary": summary},
    )
    await update_agent_run(run_id=run_id, current_step="COMPLETE", status=final_status, completed=True)
    await flush_langsmith_traces()
    await manager.broadcast(
        {
            "type": "PIPELINE_COMPLETE",
            "timestamp": datetime.utcnow().isoformat(),
            "run_id": run_id,
            "summary": summary,
            "status": final_status,
        }
    )
    return state
