"""Gmail MCP helper functions for sending and polling HR-related emails."""

from __future__ import annotations

from typing import Any

import httpx

from backend.config import settings


async def send_email(to_email: str, subject: str, html_body: str) -> dict[str, Any]:
    """Send an email via Gmail MCP and return standardized status metadata."""

    payload = {
        "action": "send_email",
        "to": to_email,
        "subject": subject,
        "html": html_body,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(settings.gmail_mcp_url, json=payload)
            response.raise_for_status()
            body = response.json() if response.text else {}
        return {
            "success": True,
            "email_id": str(body.get("id") or body.get("message_id") or ""),
            "raw": body,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def poll_reply(thread_id: str, max_results: int = 10) -> dict[str, Any]:
    """Poll Gmail MCP for thread replies and return parsed results."""

    payload = {
        "action": "poll_replies",
        "thread_id": thread_id,
        "limit": max_results,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(settings.gmail_mcp_url, json=payload)
            response.raise_for_status()
            body = response.json() if response.text else {}
        return {"success": True, "replies": body.get("replies", []), "raw": body}
    except Exception as exc:
        return {"success": False, "error": str(exc), "replies": []}
