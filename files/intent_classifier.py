"""
Intent Classifier Node
───────────────────────
Simple fast LLM call — NOT a ReAct agent.
Just reads the message and returns one label.
No tools. No loop. Just routing.
"""

from langchain_anthropic import ChatAnthropic
from ..state import MoneyState

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)

VALID_INTENTS = [
    "fire_plan",     # retirement, FIRE, SIP roadmap, invest for future
    "tax",           # tax saving, 80C, old vs new regime, Form 16
    "health_score",  # overall financial health, am I on track
    "mf_xray",       # mutual fund check, portfolio review, XIRR, overlap
    "life_event",    # bonus, marriage, baby, job change, inheritance
    "general",       # greeting, vague question, out of scope
]


async def intent_classifier_node(state: MoneyState) -> dict:
    last_msg = state["messages"][-1]["content"]

    prompt = f"""Classify this financial query into exactly ONE intent.

INTENTS:
- fire_plan     → retirement planning, FIRE, when can I retire, SIP for goals, financial independence
- tax           → save tax, 80C, 80D, old vs new regime, Form 16, HRA, NPS tax benefit
- health_score  → financial health check, am I doing okay, overall review, score my finances
- mf_xray       → check my mutual funds, portfolio analysis, XIRR, fund overlap, rebalance
- life_event    → got a bonus, getting married, having a baby, job change, received inheritance
- general       → greeting, general chat, unclear question, not finance related

USER MESSAGE:
"{last_msg}"

RULES:
- Pick the PRIMARY intent even if message has multiple topics
- fire_plan covers tax saving too (FIRE plans include 80C/NPS naturally)
- When in doubt → general

Reply with EXACTLY ONE WORD from the list above. Nothing else."""

    result = await llm.ainvoke(prompt)
    intent = result.content.strip().lower().strip('"').strip("'")

    if intent not in VALID_INTENTS:
        intent = "general"

    return {"intent": intent}
