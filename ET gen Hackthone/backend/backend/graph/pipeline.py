"""LangGraph pipeline wiring for all eight HireSignal autonomous hiring agents."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from langgraph.graph import END, START, StateGraph

from backend.agents.approval_processor import run_approval_processor
from backend.agents.audit_logger import (
    append_state_audit,
    broadcast_event,
    run_audit_logger,
    update_agent_run,
    write_audit_log,
)
from backend.agents.hiring_detector import run_hiring_detector
from backend.agents.hr_notifier import run_hr_notifier
from backend.agents.jd_generator import run_jd_generator
from backend.agents.jd_reviewer import run_jd_reviewer
from backend.agents.linkedin_poster import run_linkedin_poster
from backend.agents.workforce_monitor import run_workforce_monitor
from backend.graph.state import HireSignalState


NodeFn = Callable[[HireSignalState], Awaitable[HireSignalState]]


async def _execute_node(
    state: HireSignalState,
    agent_name: str,
    run_step: str,
    node_fn: NodeFn,
) -> HireSignalState:
    """Execute one agent node with guaranteed audit logging and WebSocket broadcasting."""

    run_id = state.get("run_id", "")
    state.setdefault("errors", [])
    state.setdefault("audit_entries", [])

    await update_agent_run(run_id=run_id, current_step=run_step, status="RUNNING")
    await write_audit_log(
        agent_name=agent_name,
        action=f"{run_step} started",
        outcome="SUCCESS",
        metadata={"run_id": run_id, "department": state.get("department")},
    )
    await append_state_audit(
        state,
        agent_name=agent_name,
        action=f"{run_step} started",
        outcome="SUCCESS",
        metadata={"run_id": run_id},
    )
    await broadcast_event(
        agent_name=agent_name,
        action=f"{run_step} started",
        status="SUCCESS",
        extra={"run_id": run_id},
    )

    errors_before = len(state.get("errors", []))
    try:
        updated = await node_fn(state)
    except Exception as exc:
        state["errors"].append(f"{agent_name}: {exc}")
        await write_audit_log(
            agent_name=agent_name,
            action=f"{run_step} failed",
            outcome="ERROR",
            metadata={"run_id": run_id, "error": str(exc)},
        )
        await append_state_audit(
            state,
            agent_name=agent_name,
            action=f"{run_step} failed",
            outcome="ERROR",
            metadata={"run_id": run_id, "error": str(exc)},
        )
        await broadcast_event(
            agent_name=agent_name,
            action=f"{run_step} failed",
            status="ERROR",
            extra={"run_id": run_id, "error": str(exc)},
        )
        return state

    errors_after = len(updated.get("errors", []))
    completion_outcome = "WARNING" if errors_after > errors_before else "SUCCESS"

    await write_audit_log(
        agent_name=agent_name,
        action=f"{run_step} completed",
        outcome=completion_outcome,
        metadata={"run_id": run_id, "errors_count": len(updated.get("errors", []))},
    )
    await append_state_audit(
        updated,
        agent_name=agent_name,
        action=f"{run_step} completed",
        outcome=completion_outcome,
        metadata={"run_id": run_id},
    )
    await broadcast_event(
        agent_name=agent_name,
        action=f"{run_step} completed",
        status=completion_outcome,
        extra={"run_id": run_id},
    )
    return updated


async def workforce_monitor_node(state: HireSignalState) -> HireSignalState:
    """Run agent 1 workforce monitoring node with standard instrumentation."""

    return await _execute_node(state, "workforce_monitor", "WORKFORCE_MONITOR", run_workforce_monitor)


async def hiring_detector_node(state: HireSignalState) -> HireSignalState:
    """Run agent 2 hiring detector node with standard instrumentation."""

    return await _execute_node(state, "hiring_detector", "HIRING_DETECTOR", run_hiring_detector)


async def hr_notifier_node(state: HireSignalState) -> HireSignalState:
    """Run agent 3 HR notifier node with standard instrumentation."""

    return await _execute_node(state, "hr_notifier", "HR_NOTIFIER", run_hr_notifier)


async def approval_processor_node(state: HireSignalState) -> HireSignalState:
    """Run agent 4 approval processor node with standard instrumentation."""

    return await _execute_node(state, "approval_processor", "APPROVAL_PROCESSOR", run_approval_processor)


async def jd_generator_node(state: HireSignalState) -> HireSignalState:
    """Run agent 5 JD generator node with standard instrumentation."""

    return await _execute_node(state, "jd_generator", "JD_GENERATOR", run_jd_generator)


async def jd_reviewer_node(state: HireSignalState) -> HireSignalState:
    """Run agent 6 JD reviewer node with standard instrumentation."""

    return await _execute_node(state, "jd_reviewer", "JD_REVIEWER", run_jd_reviewer)


async def linkedin_poster_node(state: HireSignalState) -> HireSignalState:
    """Run agent 7 LinkedIn posting node with standard instrumentation."""

    return await _execute_node(state, "linkedin_poster", "LINKEDIN_POSTER", run_linkedin_poster)


async def audit_logger_node(state: HireSignalState) -> HireSignalState:
    """Run agent 8 final audit logging node with standard instrumentation."""

    return await _execute_node(state, "audit_logger", "AUDIT_LOGGER", run_audit_logger)


def _route_after_hiring_detector(state: HireSignalState) -> str:
    """Branch after hiring detector based on HIRE vs NO_HIRE decision."""

    decision = str(state.get("hiring_decision", {}).get("decision", "NO_HIRE")).upper()
    if decision == "HIRE":
        return "to_hr_notifier"
    return "to_audit"


def _route_after_approval_processor(state: HireSignalState) -> str:
    """Branch after approval processor based on HR approval outcome."""

    if state.get("hr_approved") is True:
        return "to_jd_generator"
    return "to_audit"


def _route_after_jd_reviewer(state: HireSignalState) -> str:
    """Branch after JD review, retrying JD generation once if needed."""

    if state.get("jd_approved") is True:
        return "to_linkedin"

    retry_count = int(state.get("jd_retry_count", 0) or 0)
    if retry_count <= 1:
        return "retry_jd"
    return "to_audit"


async def create_graph(store: Any, checkpointer: Any):
    """Construct and compile the HireSignal graph with provided store and checkpointer."""

    graph = StateGraph(HireSignalState)

    graph.add_node("workforce_monitor_node", workforce_monitor_node)
    graph.add_node("hiring_detector_node", hiring_detector_node)
    graph.add_node("hr_notifier_node", hr_notifier_node)
    graph.add_node("approval_processor_node", approval_processor_node)
    graph.add_node("jd_generator_node", jd_generator_node)
    graph.add_node("jd_reviewer_node", jd_reviewer_node)
    graph.add_node("linkedin_poster_node", linkedin_poster_node)
    graph.add_node("audit_logger_node", audit_logger_node)

    graph.add_edge(START, "workforce_monitor_node")
    graph.add_edge("workforce_monitor_node", "hiring_detector_node")

    graph.add_conditional_edges(
        "hiring_detector_node",
        _route_after_hiring_detector,
        {
            "to_hr_notifier": "hr_notifier_node",
            "to_audit": "audit_logger_node",
        },
    )

    graph.add_edge("hr_notifier_node", "approval_processor_node")

    graph.add_conditional_edges(
        "approval_processor_node",
        _route_after_approval_processor,
        {
            "to_jd_generator": "jd_generator_node",
            "to_audit": "audit_logger_node",
        },
    )

    graph.add_edge("jd_generator_node", "jd_reviewer_node")

    graph.add_conditional_edges(
        "jd_reviewer_node",
        _route_after_jd_reviewer,
        {
            "to_linkedin": "linkedin_poster_node",
            "retry_jd": "jd_generator_node",
            "to_audit": "audit_logger_node",
        },
    )

    graph.add_edge("linkedin_poster_node", "audit_logger_node")
    graph.add_edge("audit_logger_node", END)

    return graph.compile(checkpointer=checkpointer, store=store)
