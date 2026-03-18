"""Slack webhook helper for notifying recruiting and hiring stakeholders."""

from __future__ import annotations

from typing import Any

import httpx

from backend.config import settings


async def send_slack_message(message: str) -> dict[str, Any]:
    """Send a message to Slack via incoming webhook and return status metadata."""

    if not settings.slack_webhook_url:
        return {"success": False, "error": "SLACK_WEBHOOK_URL is not configured."}

    payload = {"text": message}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(settings.slack_webhook_url, json=payload)
            response.raise_for_status()
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
