"""Google Calendar MCP helper used to reserve interview windows after job posting."""

from __future__ import annotations

from typing import Any

import httpx

from backend.config import settings


async def create_calendar_event(
    title: str,
    start_iso: str,
    end_iso: str,
    description: str,
) -> dict[str, Any]:
    """Create a calendar event through the configured Google Calendar MCP endpoint."""

    payload = {
        "action": "create_event",
        "title": title,
        "start": start_iso,
        "end": end_iso,
        "description": description,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(settings.gcal_mcp_url, json=payload)
            response.raise_for_status()
            body = response.json() if response.text else {}
        return {
            "success": True,
            "event_id": str(body.get("id") or body.get("event_id") or ""),
            "raw": body,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}
