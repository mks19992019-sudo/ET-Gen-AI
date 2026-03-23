"""
Health Score Agent — ReAct agent for financial wellness scoring
───────────────────────────────────────────────────────────────
Tools: sip_calculator, tax_saving_options, insurance_checker
Scores user across 6 dimensions and gives improvement plan.
"""

import json
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from ..state import MoneyState

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)


async def health_react_agent(state: MoneyState) -> dict:
    profile = state["profile"]

    async with MultiServerMCPClient({
        "finance_tools": {
            "url":       "http://localhost:8001/sse",
            "transport": "sse",
        }
    }) as mcp_client:
        tools = mcp_client.get_tools()

        health_tools = [
            t for t in tools
            if t.name in [
                "sip_calculator",
                "tax_saving_options",
                "insurance_checker",
            ]
        ]

        system = f"""You are a financial health coach for India.

USER PROFILE:
{json.dumps(profile, indent=2)}

YOUR JOB:
Use your tools to check their situation, then score them across 6 dimensions.

SCORING DIMENSIONS (0 to 100 each):
1. Emergency Fund    → do they have 6 months expenses saved?
2. Insurance         → adequate term + health coverage?
3. Investments       → diversified? regular SIP?
4. Debt Health       → EMI below 40% of income?
5. Tax Efficiency    → using 80C / NPS / HRA fully?
6. Retirement Ready  → on track for retirement corpus?

RESPONSE FORMAT:
Dimension | Score | One-line reason
──────────────────────────────────
Emergency Fund  | 45/100 | Only 2 months saved, need 6
Insurance       | 70/100 | Term policy exists, no health cover
... (all 6)

Overall Score: XX/100

TOP 3 IMPROVEMENTS RIGHT NOW:
1. [specific action, specific amount, specific impact]
2. ...
3. ...

Use tool results for accurate scoring. Do not guess."""

        agent  = create_react_agent(llm, health_tools)
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
