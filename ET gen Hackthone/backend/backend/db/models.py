"""SQLAlchemy ORM models for HireSignal workforce, hiring, and audit data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


class Employee(Base):
    """Employee master data used for workforce and attrition analysis."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    department: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    hours_per_week: Mapped[float] = mapped_column(Float, nullable=False)
    skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    joined_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    exit_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    workloads: Mapped[list["Workload"]] = relationship("Workload", back_populates="employee")


class Team(Base):
    """Team-level operational metrics and staffing constraints."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    department: Mapped[str] = mapped_column(String, nullable=False)
    headcount: Mapped[int] = mapped_column(Integer, nullable=False)
    min_required: Mapped[int] = mapped_column(Integer, nullable=False)
    max_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_hours_per_week: Mapped[float] = mapped_column(Float, nullable=False, default=40.0)

    projects: Mapped[list["Project"]] = relationship("Project", back_populates="team")


class Project(Base):
    """Project demand signals tied to specific teams."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    required_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    required_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)

    team: Mapped["Team"] = relationship("Team", back_populates="projects")


class Workload(Base):
    """Weekly workload records used for utilization and stress analytics."""

    __tablename__ = "workloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    week_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    tasks_count: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_hours: Mapped[float] = mapped_column(Float, nullable=False)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="workloads")


class HiringDecision(Base):
    """Hiring recommendation and approval lifecycle record."""

    __tablename__ = "hiring_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    department: Mapped[str] = mapped_column(String, nullable=False)
    role_needed: Mapped[str] = mapped_column(String, nullable=False)
    urgency: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    jd_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_post_id: Mapped[str | None] = mapped_column(String, nullable=True)
    approval_token: Mapped[str | None] = mapped_column(String, nullable=True)
    jd_approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)


class AuditLog(Base):
    """Structured audit trail for every agent action and pipeline event."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    agent_name: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)


class AgentRun(Base):
    """Pipeline run tracker for dashboard and scheduler observability."""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    current_step: Mapped[str | None] = mapped_column(String, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String, nullable=False)
