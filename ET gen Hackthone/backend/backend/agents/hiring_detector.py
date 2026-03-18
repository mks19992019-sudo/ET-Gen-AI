"""Agent 2: calls Claude to decide whether a hiring action is needed."""

from __future__ import annotations

import ast
import json
import re
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.audit_logger import write_audit_log
from backend.config import settings
from backend.db.database import AsyncSessionLocal
from backend.db.models import HiringDecision
from backend.graph.state import HireSignalState


def _build_user_prompt(workforce_data: dict[str, Any]) -> str:
    """Build the structured user prompt from monitored workforce metrics."""

    return (
        f"Team: {workforce_data.get('team_name', '')}\n"
        f"Current headcount: {workforce_data.get('headcount', 0)} "
        f"(minimum required: {workforce_data.get('min_required', 0)})\n"
        f"Average hours per week: {workforce_data.get('avg_hours', 0)}\n"
        f"Recent exits last 90 days: {workforce_data.get('recent_exits', 0)}\n"
        f"Skill gaps for upcoming projects: {workforce_data.get('skill_gaps', [])}\n"
        f"Upcoming project deadline pressure: {workforce_data.get('deadline_pressure', 'LOW')}\n\n"
        "Rules:\n"
        "- avg_hours > 45 AND headcount < min_required => strong HIRE signal\n"
        "- recent_exits >= 2 AND headcount < min_required => HIRE signal\n"
        "- skill_gap exists for confirmed upcoming project => HIRE signal\n"
        "- If multiple signals present => urgency = HIGH\n"
        "- If one signal present => urgency = MEDIUM\n"
        "- If borderline => NO_HIRE with recommendation to monitor\n\n"
        "Respond ONLY in valid JSON:\n"
        "{\n"
        "  'decision': 'HIRE' or 'NO_HIRE',\n"
        "  'role_needed': 'specific role title',\n"
        "  'reason': 'detailed explanation',\n"
        "  'urgency': 'HIGH' or 'MEDIUM' or 'LOW'\n"
        "}"
    )


def _extract_json_payload(raw_content: Any) -> dict[str, Any]:
    """Parse model output into JSON while tolerating common formatting variants."""

    content = raw_content
    if isinstance(content, list):
        content = "\n".join(str(part) for part in content)
    content = str(content).strip()

    try:
        return json.loads(content)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        candidate = match.group(0)
        try:
            return json.loads(candidate)
        except Exception:
            try:
                return ast.literal_eval(candidate)
            except Exception:
                return {}
    return {}


def _default_decision(workforce_data: dict[str, Any]) -> dict[str, str]:
    """Return deterministic fallback decision when Claude is unavailable."""

    signals = 0
    headcount = workforce_data.get("headcount", 0)
    min_required = workforce_data.get("min_required", 0)
    avg_hours = workforce_data.get("avg_hours", 0)
    recent_exits = workforce_data.get("recent_exits", 0)
    has_skill_gap = bool(workforce_data.get("skill_gaps"))

    if avg_hours > 45 and headcount < min_required:
        signals += 1
    if recent_exits >= 2 and headcount < min_required:
        signals += 1
    if has_skill_gap:
        signals += 1

    if signals >= 2:
        decision = "HIRE"
        urgency = "HIGH"
    elif signals == 1:
        decision = "HIRE"
        urgency = "MEDIUM"
    else:
        decision = "NO_HIRE"
        urgency = "LOW"

    role_needed = "Machine Learning Engineer" if has_skill_gap else "Generalist Engineer"
    reason = (
        "Fallback decision used due to model unavailability. "
        f"Signals={signals}, headcount={headcount}/{min_required}, avg_hours={avg_hours}, "
        f"recent_exits={recent_exits}, skill_gap={has_skill_gap}."
    )
    return {
        "decision": decision,
        "role_needed": role_needed,
        "reason": reason,
        "urgency": urgency,
    }


async def _call_claude_for_decision(workforce_data: dict[str, Any]) -> dict[str, Any]:
    """Call Claude Sonnet model and parse its JSON decision response."""

    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured.")

    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0,
        anthropic_api_key=settings.anthropic_api_key,
    )
    system_prompt = (
        "You are a workforce intelligence agent for HireSignal. "
        "Analyze the provided team data and determine if hiring is needed. "
        "Be precise and data-driven. Consider all signals together holistically."
    )
    user_prompt = _build_user_prompt(workforce_data)
    result = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])

    parsed = _extract_json_payload(result.content)
    if not parsed:
        raise ValueError("Claude returned non-JSON output.")
    return parsed


async def run_hiring_detector(state: HireSignalState) -> HireSignalState:
    """Generate hiring recommendation via Claude and persist it to the database."""

    state.setdefault("errors", [])
    workforce_data = state.get("workforce_data", {})

    decision: dict[str, Any]
    try:
        decision = await _call_claude_for_decision(workforce_data)
    except Exception as exc:
        state["errors"].append(f"hiring_detector_claude: {exc}")
        await write_audit_log(
            agent_name="hiring_detector",
            action="Claude decision call failed",
            outcome="ERROR",
            metadata={"run_id": state.get("run_id"), "error": str(exc)},
        )
        decision = _default_decision(workforce_data)

    decision_normalized = {
        "decision": str(decision.get("decision", "NO_HIRE")).upper(),
        "role_needed": str(decision.get("role_needed", "Generalist Engineer")),
        "reason": str(decision.get("reason", "No reason provided.")),
        "urgency": str(decision.get("urgency", "LOW")).upper(),
    }
    state["hiring_decision"] = decision_normalized

    try:
        async with AsyncSessionLocal() as session:
            row = HiringDecision(
                department=state.get("department", ""),
                role_needed=decision_normalized["role_needed"],
                urgency=decision_normalized["urgency"],
                reason=decision_normalized["reason"],
                status="PENDING_HR_APPROVAL",
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            state["decision_id"] = row.id
    except Exception as exc:
        state["errors"].append(f"hiring_detector_db: {exc}")
        await write_audit_log(
            agent_name="hiring_detector",
            action="Failed to persist HiringDecision",
            outcome="ERROR",
            metadata={"run_id": state.get("run_id"), "error": str(exc)},
        )
        state["decision_id"] = None

    return state
