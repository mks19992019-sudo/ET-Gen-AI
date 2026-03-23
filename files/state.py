from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages


class UserProfile(TypedDict):
    """
    Builds up over time from conversations.
    Every field starts as None — gets filled as user shares info.
    Agent NEVER asks for a field that is already filled.
    """
    age:            Optional[int]
    income:         Optional[float]     # annual, rupees
    expenses:       Optional[float]     # monthly, rupees
    risk:           Optional[str]       # conservative / moderate / aggressive
    tax_bracket:    Optional[float]     # 5.0 / 20.0 / 30.0
    goals:          list                # [{"type": "retirement", "target_age": 45}]
    investments:    dict                # {"hdfc_flexi_cap": 200000, "ppf": 50000}
    insurance:      dict                # {"term": True, "health": False, "amount": 5000000}
    employer:       Optional[str]       # for HRA / NPS employer match checks
    city:           Optional[str]       # metro vs non-metro for HRA calc


class MoneyState(TypedDict):
    """
    Shared state that flows through every node in the graph.
    Graph is stateless — this carries everything for one run.
    Profile is loaded from DB at start, saved back at end.
    """
    # Full conversation history — LangGraph handles merging
    messages:       Annotated[list, add_messages]

    # Who is this user
    user_id:        str

    # What we know about them — grows over time
    profile:        UserProfile

    # Which agent should handle this turn
    intent:         str                 # fire_plan / tax / health_score / mf_xray / life_event / general

    # If profile is missing critical fields for the intent
    missing_field:  Optional[str]       # first missing field — clarifier asks for this

    # Final output — text for chat + data for frontend charts
    final_output:   dict                # {"text": "...", "chart_data": {}, "cards": []}
