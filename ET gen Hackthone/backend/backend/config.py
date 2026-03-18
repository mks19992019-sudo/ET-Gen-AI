"""Application configuration module loading all environment variables from .env."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Typed settings container for runtime configuration values."""

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:password@postgres:5432/hiresignal",
    )
    postgres_dsn: str = os.getenv(
        "POSTGRES_DSN",
        "postgresql://user:password@postgres:5432/hiresignal",
    )
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "")
    langchain_tracing_v2: str = os.getenv("LANGCHAIN_TRACING_V2", "true")
    langchain_project: str = os.getenv("LANGCHAIN_PROJECT", "hiresignal")
    hr_email: str = os.getenv("HR_EMAIL", "hr@company.com")
    escalation_email: str = os.getenv("ESCALATION_EMAIL", "director@company.com")
    slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
    linkedin_access_token: str = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    linkedin_person_urn: str = os.getenv("LINKEDIN_PERSON_URN", "")
    gmail_mcp_url: str = os.getenv("GMAIL_MCP_URL", "https://gmail.mcp.claude.com/mcp")
    gcal_mcp_url: str = os.getenv("GCAL_MCP_URL", "https://gcal.mcp.claude.com/mcp")
    base_url: str = os.getenv("BASE_URL", "http://localhost:8000")
    secret_key: str = os.getenv("SECRET_KEY", "change-me")


settings = Settings()

# Ensure tracing environment variables are present for LangSmith-enabled runs.
os.environ.setdefault("LANGCHAIN_TRACING_V2", settings.langchain_tracing_v2)
os.environ.setdefault("LANGCHAIN_PROJECT", settings.langchain_project)
if settings.langsmith_api_key:
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)

# Export convenient constants for modules that prefer direct imports.
DATABASE_URL = settings.database_url
DB_URI = settings.postgres_dsn
ANTHROPIC_API_KEY = settings.anthropic_api_key
LANGSMITH_API_KEY = settings.langsmith_api_key
LANGCHAIN_TRACING_V2 = settings.langchain_tracing_v2
LANGCHAIN_PROJECT = settings.langchain_project
HR_EMAIL = settings.hr_email
ESCALATION_EMAIL = settings.escalation_email
SLACK_WEBHOOK_URL = settings.slack_webhook_url
LINKEDIN_ACCESS_TOKEN = settings.linkedin_access_token
LINKEDIN_PERSON_URN = settings.linkedin_person_urn
GMAIL_MCP_URL = settings.gmail_mcp_url
GCAL_MCP_URL = settings.gcal_mcp_url
BASE_URL = settings.base_url
SECRET_KEY = settings.secret_key
