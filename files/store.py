"""
DB Store
─────────
For hackathon: JSON file store — zero setup, works immediately.
For production: swap _load_db/_save_db with Postgres async calls.

Two functions only:
  load_profile(user_id)  → UserProfile dict
  save_profile(user_id, profile)
"""

import json
import os
from .graph.state import UserProfile

DB_PATH = "data/user_profiles.json"


def _empty_profile() -> UserProfile:
    return {
        "age":         None,
        "income":      None,
        "expenses":    None,
        "risk":        None,
        "tax_bracket": None,
        "goals":       [],
        "investments": {},
        "insurance":   {},
        "employer":    None,
        "city":        None,
    }


def _load_db() -> dict:
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(DB_PATH):
        return {}
    with open(DB_PATH) as f:
        return json.load(f)


def _save_db(db: dict):
    os.makedirs("data", exist_ok=True)
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)


async def load_profile(user_id: str) -> UserProfile:
    """Load user profile from DB. Returns empty profile for new users."""
    db = _load_db()
    return db.get(user_id, _empty_profile())


async def save_profile(user_id: str, profile: UserProfile):
    """Save updated profile back to DB after every graph run."""
    db = _load_db()
    db[user_id] = profile
    _save_db(db)


async def load_message_history(user_id: str) -> list:
    """Load past messages for context (last 20 messages)."""
    path = f"data/messages_{user_id}.json"
    if not os.path.exists(path):
        return []
    with open(path) as f:
        msgs = json.load(f)
    return msgs[-20:]    # keep last 20 for context window


async def save_message(user_id: str, role: str, content: str):
    """Append one message to user's history."""
    path = f"data/messages_{user_id}.json"
    os.makedirs("data", exist_ok=True)

    msgs = []
    if os.path.exists(path):
        with open(path) as f:
            msgs = json.load(f)

    msgs.append({"role": role, "content": content})

    with open(path, "w") as f:
        json.dump(msgs, f, indent=2)
