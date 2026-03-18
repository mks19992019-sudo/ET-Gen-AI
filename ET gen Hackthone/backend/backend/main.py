"""FastAPI entrypoint with correct LangGraph/PostgreSQL lifespan initialization pattern."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore

from backend.api.routes import api_router
from backend.api.websocket import ws_router
from backend.config import DB_URI
from backend.db.database import close_db, init_db
from backend.graph.pipeline import create_graph
from backend.scheduler import configure_scheduler, shutdown_scheduler, start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB, LangGraph resources, scheduler, and cleanly shut down on exit."""

    await init_db()

    # CRITICAL: LangGraph lifecycle must remain inside FastAPI lifespan.
    async with (
        AsyncPostgresStore.from_conn_string(DB_URI) as store,
        AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer,
    ):
        await store.setup()
        await checkpointer.setup()
        app.state.graph = await create_graph(store, checkpointer)
        app.state.store = store

        configure_scheduler(app)
        start_scheduler()

        print("HireSignal backend running on http://localhost:8000")
        print("Dashboard: http://localhost:8000")
        print("API docs: http://localhost:8000/docs")

        yield

        shutdown_scheduler()

    await close_db()


app = FastAPI(title="HireSignal API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(ws_router)

# Serve frontend static files from the top-level frontend directory.
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
