"""Agent 1: collects workforce and demand signals from PostgreSQL for one team."""

from __future__ import annotations

from backend.db.database import AsyncSessionLocal
from backend.graph.state import HireSignalState
from backend.tools.sql_tools import get_team_workforce_data


async def run_workforce_monitor(state: HireSignalState) -> HireSignalState:
    """Query and attach workforce metrics for the requested department/team."""

    department = state.get("department", "")
    state.setdefault("errors", [])
    try:
        async with AsyncSessionLocal() as session:
            workforce_data = await get_team_workforce_data(session, department)
        if not workforce_data:
            raise ValueError(f"No workforce data found for team: {department}")
        state["workforce_data"] = workforce_data
    except Exception as exc:
        state["workforce_data"] = {}
        state["errors"].append(f"workforce_monitor: {exc}")
    return state
