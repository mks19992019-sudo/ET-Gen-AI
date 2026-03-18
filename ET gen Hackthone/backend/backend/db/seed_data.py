"""Seed script that loads realistic demo data for HireSignal analytics and pipeline demos."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import AsyncSessionLocal, init_db
from backend.db.models import Employee, Project, Team, Workload


def _engineering_skills() -> list[str]:
    """Return canonical engineering skill stack for seeded employees."""

    return ["Python", "React", "Node.js"]


async def _reset_tables(session: AsyncSession) -> None:
    """Delete prior data so seeding remains deterministic for demos."""

    await session.execute(delete(Workload))
    await session.execute(delete(Project))
    await session.execute(delete(Employee))
    await session.execute(delete(Team))
    await session.commit()


def _build_teams() -> list[Team]:
    """Create the exact team records requested by the specification."""

    return [
        Team(name="Engineering", department="Tech", headcount=6, min_required=8, max_capacity=10, avg_hours_per_week=52.0),
        Team(name="Design", department="Product", headcount=4, min_required=4, max_capacity=6, avg_hours_per_week=38.0),
        Team(name="Sales", department="Business", headcount=5, min_required=6, max_capacity=8, avg_hours_per_week=46.5),
    ]


def _build_employees(now: datetime) -> list[Employee]:
    """Create 15 employees with requested active/resigned distribution and workloads."""

    return [
        Employee(name="Aarav Mehta", role="Backend Engineer", department="Engineering", status="active", hours_per_week=53.0, skills=_engineering_skills(), joined_date=now - timedelta(days=600), exit_date=None),
        Employee(name="Nisha Rao", role="Frontend Engineer", department="Engineering", status="active", hours_per_week=51.5, skills=_engineering_skills(), joined_date=now - timedelta(days=540), exit_date=None),
        Employee(name="Kabir Shah", role="Full Stack Engineer", department="Engineering", status="active", hours_per_week=54.2, skills=_engineering_skills(), joined_date=now - timedelta(days=500), exit_date=None),
        Employee(name="Riya Sethi", role="DevOps Engineer", department="Engineering", status="active", hours_per_week=50.8, skills=_engineering_skills(), joined_date=now - timedelta(days=420), exit_date=None),
        Employee(name="Vihaan Kapoor", role="QA Engineer", department="Engineering", status="active", hours_per_week=52.7, skills=_engineering_skills(), joined_date=now - timedelta(days=390), exit_date=None),
        Employee(name="Ishita Das", role="Engineering Manager", department="Engineering", status="active", hours_per_week=55.0, skills=_engineering_skills(), joined_date=now - timedelta(days=720), exit_date=None),
        Employee(name="Arjun Bhat", role="ML Engineer", department="Engineering", status="resigned", hours_per_week=0.0, skills=["Python", "TensorFlow"], joined_date=now - timedelta(days=480), exit_date=now - timedelta(days=20)),
        Employee(name="Mira Joshi", role="Product Designer", department="Design", status="active", hours_per_week=37.0, skills=["Figma", "UX Research", "Prototyping"], joined_date=now - timedelta(days=410), exit_date=None),
        Employee(name="Dev Malhotra", role="UX Designer", department="Design", status="active", hours_per_week=38.5, skills=["Figma", "UI Design", "Wireframing"], joined_date=now - timedelta(days=280), exit_date=None),
        Employee(name="Ananya Pillai", role="Visual Designer", department="Design", status="active", hours_per_week=36.2, skills=["Brand", "Illustration", "UI Design"], joined_date=now - timedelta(days=210), exit_date=None),
        Employee(name="Sanjay Kulkarni", role="Design Lead", department="Design", status="active", hours_per_week=39.4, skills=["Mentorship", "UX Strategy", "Design Systems"], joined_date=now - timedelta(days=800), exit_date=None),
        Employee(name="Priya Nair", role="Account Executive", department="Sales", status="active", hours_per_week=47.0, skills=["B2B", "Negotiation", "CRM"], joined_date=now - timedelta(days=300), exit_date=None),
        Employee(name="Rahul Verma", role="Sales Manager", department="Sales", status="active", hours_per_week=46.5, skills=["Leadership", "Enterprise Sales", "Forecasting"], joined_date=now - timedelta(days=520), exit_date=None),
        Employee(name="Tara Chawla", role="Sales Development Rep", department="Sales", status="resigned", hours_per_week=0.0, skills=["Prospecting", "Outbound", "CRM"], joined_date=now - timedelta(days=190), exit_date=now - timedelta(days=35)),
        Employee(name="Neel Arora", role="Account Manager", department="Sales", status="resigned", hours_per_week=0.0, skills=["Renewals", "Relationship Building", "CRM"], joined_date=now - timedelta(days=350), exit_date=now - timedelta(days=50)),
    ]


def _build_projects(team_map: dict[str, Team], now: datetime) -> list[Project]:
    """Create projects, including an upcoming engineering project with ML skill gap."""

    return [
        Project(
            name="DeepSearch AI",
            team_id=team_map["Engineering"].id,
            required_skills=["Python", "ML", "LLM"],
            deadline=now + timedelta(days=30),
            required_hours=320,
            status="upcoming",
        ),
        Project(
            name="Dashboard Redesign",
            team_id=team_map["Design"].id,
            required_skills=["Figma", "Design Systems"],
            deadline=now + timedelta(days=20),
            required_hours=180,
            status="active",
        ),
        Project(
            name="Q2 Enterprise Push",
            team_id=team_map["Sales"].id,
            required_skills=["Enterprise Sales", "CRM"],
            deadline=now + timedelta(days=45),
            required_hours=220,
            status="active",
        ),
    ]


def _workload_band(department: str) -> tuple[float, float]:
    """Return min and max weekly workload band for the specified department."""

    if department == "Engineering":
        return (50.0, 58.0)
    if department == "Design":
        return (35.0, 40.0)
    return (44.0, 50.0)


async def _build_workloads(session: AsyncSession, employees: list[Employee], now: datetime) -> None:
    """Insert four weeks of workload history for each employee."""

    workload_rows: list[Workload] = []
    for employee in employees:
        min_hours, max_hours = _workload_band(employee.department)
        for week in range(4):
            week_start = now - timedelta(days=7 * (week + 1))
            span = max_hours - min_hours
            estimated = min_hours + ((employee.id or 1) * (week + 2) % 10) / 10 * span
            workload_rows.append(
                Workload(
                    employee_id=employee.id,
                    week_start=week_start,
                    tasks_count=18 + ((employee.id or 1) + week) % 7,
                    estimated_hours=round(estimated, 2),
                )
            )
    session.add_all(workload_rows)
    await session.commit()


async def seed_database() -> None:
    """Initialize schema and seed all demo records in one transaction flow."""

    await init_db()
    now = datetime.utcnow()

    async with AsyncSessionLocal() as session:
        await _reset_tables(session)

        teams = _build_teams()
        session.add_all(teams)
        await session.commit()

        for team in teams:
            await session.refresh(team)

        employees = _build_employees(now)
        session.add_all(employees)
        await session.commit()

        for employee in employees:
            await session.refresh(employee)

        team_map = {team.name: team for team in teams}
        projects = _build_projects(team_map, now)
        session.add_all(projects)
        await session.commit()

        await _build_workloads(session, employees, now)

    print("HireSignal seed complete: teams, employees, projects, and workloads inserted.")


def main() -> None:
    """Entrypoint for `python -m backend.db.seed_data` execution."""

    asyncio.run(seed_database())


if __name__ == "__main__":
    main()
