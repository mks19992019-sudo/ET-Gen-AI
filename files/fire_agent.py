"""
FIRE Agent — ReAct agent for retirement planning
─────────────────────────────────────────────────
This is a full ReAct agent — it loops:
  Think → call MCP tool → observe result → think → call tool → ... → respond

Tools it uses (from MCP server):
  - fire_corpus_calculator
  - sip_calculator
  - tax_saving_options
  - insurance_checker
"""

import json
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from ..state import MoneyState

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)


async def fire_react_agent(state: MoneyState) -> dict:
    profile = state["profile"]

    # Connect to MCP server and get tools
    async with MultiServerMCPClient({
        "finance_tools": {
            "url":       "http://localhost:8001/sse",
            "transport": "sse",
        }
    }) as mcp_client:
        tools = mcp_client.get_tools()

        # Filter to only FIRE-relevant tools
        fire_tools = [
            t for t in tools
            if t.name in [
                "fire_corpus_calculator",
                "sip_calculator",
                "tax_saving_options",
                "insurance_checker",
            ]
        ]

        system = f"""You are an expert FIRE (Financial Independence, Retire Early) planner for India.

USER PROFILE — already known, DO NOT ask for any of this again:
{json.dumps(profile, indent=2)}

YOUR JOB — use your tools step by step:
1. Calculate FIRE corpus needed using fire_corpus_calculator
2. Calculate monthly SIP breakdown using sip_calculator
   (split: 70% equity Nifty50 index, 20% debt, 10% gold)
3. Find tax saving gaps using tax_saving_options
4. Check insurance coverage using insurance_checker

RESPONSE FORMAT:
- Give exact ₹ numbers (not ranges)
- Use Indian products: ELSS, Nifty50 index fund, PPF, NPS, SGB
- Keep under 400 words
- End with: "Your next step: [ONE specific action with amount]"

IMPORTANT: Use the real numbers from user profile.
Do not use example or placeholder numbers."""

        agent  = create_react_agent(llm, fire_tools)
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
