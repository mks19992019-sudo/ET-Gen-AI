'''Edit nedded in this file -> to replace json file with sqlite'''


"""
Profile Extractor Node
──────────────────────
Runs on EVERY message — first node always.
Silently extracts any financial info the user mentioned.
Merges into existing profile — never overwrites with None.
User never fills a form. Profile builds naturally over conversations.
"""

import json
from langchain_anthropic import ChatAnthropic
from state import MoneyState

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)


async def profile_extractor_node(state: MoneyState) -> dict:
    last_msg = state["messages"][-1]["content"]
    current  = state["profile"]

    prompt = f"""You extract financial profile information from user messages.

CURRENT KNOWN PROFILE:
{json.dumps(current, indent=2)}

USER MESSAGE:
"{last_msg}"

TASK:
Extract ONLY what is explicitly mentioned in this message.
Return a JSON object with only the NEW or UPDATED fields.
If nothing financial is mentioned, return {{}}.

EXTRACTABLE FIELDS:
- age (integer, years)
- income (float, annual rupees — convert if monthly: multiply by 12)
- expenses (float, monthly rupees)
- risk ("conservative" | "moderate" | "aggressive")
- tax_bracket (float: 5.0 | 20.0 | 30.0)
- goals (list: [{{"type": "retirement", "target_age": 45}}])
- investments (dict: {{"fund_name_or_type": amount_in_rupees}})
- insurance (dict: {{"term": bool, "health": bool, "amount": rupees}})
- employer (string)
- city (string)

RULES:
- Never return a field as null or None
- Only include fields that appear in THIS message
- Convert "18 lakh" → 1800000, "60k" → 60000 etc
- If user says "I earn ₹1.5L/month" → income = 1800000 (annual)

Return raw JSON only. No explanation. No markdown."""

    result = await llm.ainvoke(prompt)

    try:
        raw     = result.content.strip()
        # Strip markdown if model wraps it
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        new_info = json.loads(raw.strip())

        # Merge — only update fields that have real values
        updated = {**current}
        for k, v in new_info.items():
            if v is not None and v != "" and v != {} and v != []:
                updated[k] = v

        return {"profile": updated}

    except Exception:
        # Extraction failed — no update, continue graph
        return {}
