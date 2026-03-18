"""Async SQL query utilities used by agents, API routes, and scheduler logic."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Employee, Project, Team, Workload


async def get_team_names(session: AsyncSession) -> list[str]:
    """Return all team names ordered alphabetically."""

    result = await session.execute(select(Team.name).order_by(Team.name.asc()))
    return list(result.scalars().all())


async def calculate_team_average_hours(session: AsyncSession, team_name: str) -> float:
    """Compute average estimated weekly hours for active team members over the last four weeks."""

    lookback = datetime.utcnow() - timedelta(days=28)
    stmt = (
        select(func.avg(Workload.estimated_hours))
        .join(Employee, Employee.id == Workload.employee_id)
        .where(Employee.department == team_name)
        .where(Employee.status == "active")
        .where(Workload.week_start >= lookback)
    )
    value = (await session.execute(stmt)).scalar_one_or_none()
    return round(float(value or 0.0), 2)


async def calculate_recent_exits(session: AsyncSession, team_name: str, days: int = 90) -> int:
    """Count employees who resigned from a team in the last N days."""

    cutoff = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(func.count(Employee.id))
        .where(Employee.department == team_name)
        .where(Employee.status == "resigned")
        .where(Employee.exit_date.is_not(None))
        .where(Employee.exit_date >= cutoff)
    )
    return int((await session.execute(stmt)).scalar_one() or 0)


async def calculate_total_attrition(session: AsyncSession, team_name: str) -> int:
    """Count total resigned employees for a team, regardless of date."""

    stmt = (
        select(func.count(Employee.id))
        .where(Employee.department == team_name)
        .where(Employee.status == "resigned")
    )
    return int((await session.execute(stmt)).scalar_one() or 0)


async def get_team_skill_inventory(session: AsyncSession, team_name: str) -> set[str]:
    """Return a de-duplicated set of skills from active employees in the team."""

    stmt = select(Employee.skills).where(Employee.department == team_name).where(Employee.status == "active")
    rows = (await session.execute(stmt)).scalars().all()
    skills: set[str] = set()
    for employee_skills in rows:
        for skill in employee_skills or []:
            skills.add(skill)
    return skills


async def get_upcoming_projects(session: AsyncSession, team_name: str, days: int = 60) -> list[Project]:
    """Return team projects due within N days that are active or upcoming."""

    horizon = datetime.utcnow() + timedelta(days=days)
    stmt = (
        select(Project)
        .join(Team, Team.id == Project.team_id)
        .where(Team.name == team_name)
        .where(Project.deadline <= horizon)
        .where(Project.status.in_(["active", "upcoming"]))
        .order_by(Project.deadline.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


def calculate_deadline_pressure(projects: list[Project]) -> str:
    """Translate upcoming project timelines into a simple pressure signal."""

    if not projects:
        return "LOW"
    closest_days = min((project.deadline - datetime.utcnow()).days for project in projects)
    if closest_days <= 30:
        return "HIGH"
    if closest_days <= 45:
        return "MEDIUM"
    return "LOW"


async def get_team_workforce_data(session: AsyncSession, team_name: str) -> dict[str, Any]:
    """Build the structured workforce dataset consumed by the hiring detector agent."""

    team = (await session.execute(select(Team).where(Team.name == team_name))).scalar_one_or_none()
    if team is None:
        return {}

    active_headcount_stmt = (
        select(func.count(Employee.id))
        .where(Employee.department == team_name)
        .where(Employee.status == "active")
    )
    headcount = int((await session.execute(active_headcount_stmt)).scalar_one() or 0)

    avg_hours = await calculate_team_average_hours(session, team_name)
    recent_exits = await calculate_recent_exits(session, team_name)
    team_skills = await get_team_skill_inventory(session, team_name)
    upcoming_projects = await get_upcoming_projects(session, team_name, days=60)

    skill_gaps: list[dict[str, Any]] = []
    for project in upcoming_projects:
        missing = sorted(set(project.required_skills or []) - team_skills)
        if missing:
            skill_gaps.append(
                {
                    "project": project.name,
                    "missing_skills": missing,
                    "deadline": project.deadline.isoformat(),
                    "required_hours": project.required_hours,
                }
            )

    # Keep Team snapshot metrics fresh for dashboard APIs.
    team.headcount = headcount
    team.avg_hours_per_week = avg_hours
    await session.commit()

    return {
        "team_name": team.name,
        "department": team.department,
        "headcount": headcount,
        "min_required": team.min_required,
        "max_capacity": team.max_capacity,
        "avg_hours": avg_hours,
        "recent_exits": recent_exits,
        "team_skills": sorted(team_skills),
        "skill_gaps": skill_gaps,
        "upcoming_projects": [
            {
                "name": project.name,
                "deadline": project.deadline.isoformat(),
                "required_skills": project.required_skills,
                "required_hours": project.required_hours,
                "status": project.status,
            }
            for project in upcoming_projects
        ],
        "deadline_pressure": calculate_deadline_pressure(upcoming_projects),
    }


async def get_all_teams_dashboard_data(session: AsyncSession) -> list[dict[str, Any]]:
    """Return all teams with computed status for dashboard cards."""

    teams = list((await session.execute(select(Team).order_by(Team.name.asc()))).scalars().all())
    records: list[dict[str, Any]] = []
    for team in teams:
        workforce = await get_team_workforce_data(session, team.name)
        if not workforce:
            continue
        overloaded = workforce["headcount"] < workforce["min_required"] and workforce["avg_hours"] > 45
        warning = workforce["headcount"] < workforce["min_required"] or workforce["avg_hours"] > 45
        status = "OVERLOADED" if overloaded else ("WARNING" if warning else "NORMAL")
        records.append(
            {
                "id": team.id,
                "name": team.name,
                "department": team.department,
                "headcount": workforce["headcount"],
                "min_required": team.min_required,
                "avg_hours_per_week": workforce["avg_hours"],
                "status": status,
            }
        )
    return records


async def get_all_employees(session: AsyncSession) -> list[dict[str, Any]]:
    """Return all employee records formatted for API responses."""

    rows = list((await session.execute(select(Employee).order_by(Employee.id.asc()))).scalars().all())
    return [
        {
            "id": employee.id,
            "name": employee.name,
            "role": employee.role,
            "department": employee.department,
            "status": employee.status,
            "hours_per_week": employee.hours_per_week,
            "skills": employee.skills,
            "joined_date": employee.joined_date.isoformat() if employee.joined_date else None,
            "exit_date": employee.exit_date.isoformat() if employee.exit_date else None,
        }
        for employee in rows
    ]


async def get_team_signal_scores(session: AsyncSession) -> list[dict[str, Any]]:
    """Compute signal metrics for each team used by dashboard and manual-run filtering."""

    teams = list((await session.execute(select(Team).order_by(Team.name.asc()))).scalars().all())
    signals: list[dict[str, Any]] = []
    for team in teams:
        data = await get_team_workforce_data(session, team.name)
        if not data:
            continue
        overload_pct = min(max(((data["avg_hours"] - 40.0) / 40.0) * 100.0, 0.0), 100.0)
        if data["min_required"] > 0:
            capacity_gap_pct = max(((data["min_required"] - data["headcount"]) / data["min_required"]) * 100.0, 0.0)
        else:
            capacity_gap_pct = 0.0
        exits_count = await calculate_recent_exits(session, team.name)
        attrition_count = await calculate_total_attrition(session, team.name)
        skill_gap = data["skill_gaps"]
        signals.append(
            {
                "team": team.name,
                "overload_pct": round(overload_pct, 2),
                "exits_count": exits_count,
                "capacity_gap_pct": round(capacity_gap_pct, 2),
                "attrition_count": attrition_count,
                "skill_gap": skill_gap,
            }
        )
    return signals


async def get_flagged_teams(session: AsyncSession) -> list[str]:
    """Return teams with at least one strong hiring-related signal above threshold."""

    signals = await get_team_signal_scores(session)
    flagged: list[str] = []
    for item in signals:
        has_signal = (
            item["overload_pct"] > 10
            or item["capacity_gap_pct"] > 0
            or item["exits_count"] >= 1
            or bool(item["skill_gap"])
        )
        if has_signal:
            flagged.append(item["team"])
    return flagged
