"""
Life Event Agent — ReAct agent for life-triggered financial decisions
──────────────────────────────────────────────────────────────────────
Handles: bonus, marriage, new baby, job change, inheritance
Tools: sip_calculator, tax_calculator, insurance_checker
"""

import json
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from ..state import MoneyState

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)


async def life_event_react_agent(state: MoneyState) -> dict:
    profile  = state["profile"]
    last_msg = state["messages"][-1]["content"]

    async with MultiServerMCPClient({
        "finance_tools": {
            "url":       "http://localhost:8001/sse",
            "transport": "sse",
        }
    }) as mcp_client:
        tools = mcp_client.get_tools()

        life_tools = [
            t for t in tools
            if t.name in [
                "sip_calculator",
                "tax_calculator",
                "insurance_checker",
                "tax_saving_options",
            ]
        ]

        system = f"""You are a financial advisor specialising in life event planning for India.

USER PROFILE:
{json.dumps(profile, indent=2)}

LIFE EVENT MENTIONED:
"{last_msg}"

COMMON LIFE EVENTS AND WHAT TO CHECK:
- Bonus received     → tax impact, invest vs prepay loan, split strategy
- Getting married    → combined income planning, joint investments, insurance update
- New baby           → education corpus (Sukanya/MF), insurance increase, emergency fund top-up
- Job change         → PF transfer, salary negotiation, new CTC tax optimisation
- Inheritance        → tax on inheritance (none in India), investment plan for lump sum

YOUR JOB:
1. Identify the life event from their message
2. Use relevant tools to calculate exact numbers
3. Give a specific action plan for THIS event

Be specific to their income/profile. No generic advice."""

        agent  = create_react_agent(llm, life_tools)
        result = await agent.ainvoke({
            "messages": [
                {"role": "system",  "content": system},
                *state["messages"],
            ]
        })

    final_text = result["messages"][-1].content

    return {
        "messages":     [{"role": "assistant", "content": final_text}],
        "final_output": {"text": final_text, "chart_data": {}, "cards": []},
    }
