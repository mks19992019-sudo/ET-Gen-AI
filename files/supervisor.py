"""
Supervisor — Main LangGraph Graph
───────────────────────────────────
Wires all nodes and agents together.
Entry point for every user message.

Flow:
  profile_extractor → intent_classifier → [should_clarify edge]
    → clarifier (if missing info)
    → fire_agent / tax_agent / health_agent / mf_agent / life_event_agent / END
"""

from langgraph.graph import StateGraph, END

from .state import MoneyState
from .nodes.profile_extractor import profile_extractor_node
from .nodes.intent_classifier  import intent_classifier_node
from .nodes.clarifier          import clarifier_node
from .agents.fire_agent        import fire_react_agent
from .agents.tax_agent         import tax_react_agent
from .agents.health_agent      import health_react_agent
from .agents.mf_agent          import mf_react_agent
from .agents.life_event_agent  import life_event_react_agent
from .edges                    import should_clarify


def build_graph():
    g = StateGraph(MoneyState)

    # ── Nodes ────────────────────────────────────────────────
    # Simple nodes (fast LLM calls, no tools)
    g.add_node("profile_extractor", profile_extractor_node)
    g.add_node("intent_classifier", intent_classifier_node)
    g.add_node("clarifier",         clarifier_node)

    # ReAct agents (tool-calling loops)
    g.add_node("fire_agent",        fire_react_agent)
    g.add_node("tax_agent",         tax_react_agent)
    g.add_node("health_agent",      health_react_agent)
    g.add_node("mf_agent",          mf_react_agent)
    g.add_node("life_event_agent",  life_event_react_agent)

    # ── Edges ────────────────────────────────────────────────
    # Always start here
    g.set_entry_point("profile_extractor")

    # Profile extracted → classify intent
    g.add_edge("profile_extractor", "intent_classifier")

    # After classify → check if we have enough info
    # should_clarify returns intent name or "clarify"
    g.add_conditional_edges(
        "intent_classifier",
        should_clarify,
        {
            "clarify":          "clarifier",
            "fire_plan":        "fire_agent",
            "tax":              "tax_agent",
            "health_score":     "health_agent",
            "mf_xray":          "mf_agent",
            "life_event":       "life_event_agent",
            "general":          END,    # LLM answers directly, no tools needed
        }
    )

    # Clarifier just asks one question then stops — user replies next turn
    g.add_edge("clarifier", END)

    # All agents finish → END
    g.add_edge("fire_agent",       END)
    g.add_edge("tax_agent",        END)
    g.add_edge("health_agent",     END)
    g.add_edge("mf_agent",         END)
    g.add_edge("life_event_agent", END)

    return g.compile()


# Single compiled graph instance — reused across all requests
graph = build_graph()
