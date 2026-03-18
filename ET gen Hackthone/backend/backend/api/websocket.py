"""WebSocket live-stream endpoint and connection manager for agent execution events."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


class ConnectionManager:
    """Maintain active WebSocket clients and broadcast JSON event messages."""

    def __init__(self) -> None:
        """Initialize in-memory collection of active WebSocket connections."""

        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection and track it for broadcasts."""

        await websocket.accept()
        self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket from active connection tracking."""

        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        """Send a JSON-serialized message to all connected clients safely."""

        dead_connections: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                dead_connections.append(connection)
        for connection in dead_connections:
            await self.disconnect(connection)


manager = ConnectionManager()
ws_router = APIRouter(tags=["websocket"])


@ws_router.websocket("/ws/agent-live")
async def agent_live_websocket(websocket: WebSocket) -> None:
    """Stream live agent activity updates and send heartbeat pings every 30 seconds."""

    await manager.connect(websocket)
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "PING",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )
                )
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)
