"""LinkedIn API helper for publishing approved jobs as UGC posts."""

from __future__ import annotations

from typing import Any

import httpx

from backend.config import settings


async def post_linkedin_job(role_needed: str, department: str, jd_text: str) -> dict[str, Any]:
    """Post a hiring message to LinkedIn and return the post identifier and URL when available."""

    if not settings.linkedin_access_token or not settings.linkedin_person_urn:
        return {"success": False, "error": "LinkedIn credentials are not configured."}

    post_body = {
        "author": settings.linkedin_person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": (
                        f"We are hiring: {role_needed} ({department})\\n\\n"
                        f"{jd_text[:900]}\\n\\nApply now via HireSignal."
                    )
                },
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    headers = {
        "Authorization": f"Bearer {settings.linkedin_access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.linkedin.com/v2/ugcPosts",
                headers=headers,
                json=post_body,
            )
            response.raise_for_status()
            body = response.json() if response.text else {}
            post_id = str(body.get("id") or response.headers.get("x-restli-id") or "")
        post_url = f"https://www.linkedin.com/feed/update/{post_id}" if post_id else ""
        return {"success": True, "post_id": post_id, "post_url": post_url, "raw": body}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
