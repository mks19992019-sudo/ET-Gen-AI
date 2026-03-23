"""
Edges — Routing Logic
──────────────────────
These functions decide where the graph goes next.
Two decisions:
  1. After intent_classifier → do we have enough info, or ask user first?
  2. Direct routing after clarifier answers are collected
"""

from .state import MoneyState

# Minimum fields needed before each agent can give useful advice
REQUIRED_FIELDS = {
    "fire_plan":    ["age", "income", "expenses"],
    "tax":          ["income"],
    "health_score": ["age", "income"],
    "mf_xray":      ["investments"],
    "life_event":   ["income"],
    "general":      [],
}


def should_clarify(state: MoneyState) -> str:
    """
    Called after intent_classifier.
    Checks if we have the minimum fields for this intent.
    Returns intent name to route to the right agent, or "clarify".
    """
    intent  = state["intent"]
    profile = state["profile"]

    required = REQUIRED_FIELDS.get(intent, [])
    missing  = [f for f in required if not profile.get(f)]

    if missing:
        # Store the FIRST missing field for clarifier to ask about
        state["missing_field"] = missing[0]
        return "clarify"

    # All good — route to the correct agent
    return intent
