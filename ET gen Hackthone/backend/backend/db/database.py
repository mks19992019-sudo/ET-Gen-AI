"""Async SQLAlchemy database setup and lifecycle helpers for HireSignal."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from backend.config import DATABASE_URL


Base = declarative_base()

# Global async engine/session factory used across API handlers and agents.
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, future=True)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session for FastAPI dependency injection."""

    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all database tables if they do not already exist."""

    from backend.db import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose database engine connections during app shutdown."""

    await engine.dispose()
