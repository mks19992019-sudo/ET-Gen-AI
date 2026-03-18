"""Agent 5: generates a professional job description using Claude Sonnet."""

from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select

from backend.agents.audit_logger import write_audit_log
from backend.config import settings
from backend.db.database import AsyncSessionLocal
from backend.db.models import HiringDecision
from backend.graph.state import HireSignalState


def _default_jd(role_needed: str, department: str, reason: str) -> str:
    """Create a fallback JD template when model generation is unavailable."""

    return (
        f"About the Role\n{role_needed} in {department} will help scale our hiring priorities.\n\n"
        "Key Responsibilities\n"
        "- Deliver team goals with cross-functional partners\n"
        "- Own projects end-to-end\n"
        "- Improve engineering and delivery quality\n"
        "- Mentor teammates and share best practices\n"
        "- Collaborate with product and design\n"
        "- Support high-priority launches\n\n"
        "Required Skills\n"
        "- Strong communication\n"
        "- Problem-solving mindset\n"
        "- Relevant technical/domain expertise\n"
        "- Collaboration and ownership\n"
        "- Ability to work in fast-paced teams\n\n"
        "Nice to Have\n"
        "- Experience in growth-stage startups\n"
        "- Prior mentoring experience\n"
        "- Familiarity with modern tooling\n\n"
        "What We Offer\n"
        "- Competitive salary range\n"
        "- Health benefits\n"
        "- Flexible hybrid work\n"
        "- Learning and growth opportunities\n\n"
        "Location and work type\nHybrid / Remote-friendly\n\n"
        f"Team context: {reason}"
    )


def _build_jd_prompt(role_needed: str, department: str, reason: str) -> str:
    """Build Claude user prompt for generating a full job description."""

    return (
        "Generate a complete Job Description for:\n"
        f"Role: {role_needed}\n"
        f"Department: {department}\n"
        "Company context: A growing tech company\n"
        f"Team context: {reason}\n\n"
        "Include these sections:\n"
        "1. About the Role (3-4 lines)\n"
        "2. Key Responsibilities (6-8 bullet points)\n"
        "3. Required Skills (5-6 bullet points)\n"
        "4. Nice to Have (3-4 bullet points)\n"
        "5. What We Offer (4-5 bullet points - salary range, benefits, work style)\n"
        "6. Location and work type\n\n"
        "Make it engaging, modern, and specific to the role.\n"
        "Format as plain text with clear section headers."
    )


async def _call_claude_for_jd(role_needed: str, department: str, reason: str) -> str:
    """Generate job description text via Claude Sonnet."""

    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured.")

    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0.5,
        anthropic_api_key=settings.anthropic_api_key,
    )
    system_prompt = (
        "You are an expert HR professional and technical recruiter. "
        "Generate professional, attractive, and complete job descriptions."
    )
    result = await llm.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=_build_jd_prompt(role_needed, department, reason)),
        ]
    )
    return str(result.content)


async def run_jd_generator(state: HireSignalState) -> HireSignalState:
    """Produce JD text after HR approval and persist it to the hiring decision row."""

    state.setdefault("errors", [])
    if state.get("hr_approved") is not True:
        return state

    decision = state.get("hiring_decision", {})
    role_needed = str(decision.get("role_needed", "Generalist Engineer"))
    reason = str(decision.get("reason", "Growing workload and upcoming deliverables."))
    department = state.get("department", "")

    try:
        jd_text = await _call_claude_for_jd(role_needed, department, reason)
    except Exception as exc:
        state["errors"].append(f"jd_generator_claude: {exc}")
        await write_audit_log(
            agent_name="jd_generator",
            action="Claude JD generation failed",
            outcome="ERROR",
            metadata={"run_id": state.get("run_id"), "error": str(exc)},
        )
        jd_text = _default_jd(role_needed, department, reason)

    state["jd_text"] = jd_text

    decision_id = state.get("decision_id")
    if decision_id:
        try:
            async with AsyncSessionLocal() as session:
                row = (
                    await session.execute(select(HiringDecision).where(HiringDecision.id == decision_id))
                ).scalar_one_or_none()
                if row is None:
                    raise ValueError(f"Decision {decision_id} not found")
                row.jd_text = jd_text
                row.status = "JD_GENERATED"
                await session.commit()
        except Exception as exc:
            state["errors"].append(f"jd_generator_db: {exc}")
            await write_audit_log(
                agent_name="jd_generator",
                action="Failed to persist generated JD",
                outcome="ERROR",
                metadata={"run_id": state.get("run_id"), "error": str(exc)},
            )

    return state
