"""
Tax Agent — ReAct agent for tax planning
──────────────────────────────────────────
Tools: tax_calculator, tax_saving_options
"""

import json
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from ..state import MoneyState

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)


async def tax_react_agent(state: MoneyState) -> dict:
    profile = state["profile"]

    async with MultiServerMCPClient({
        "finance_tools": {
            "url":       "http://localhost:8001/sse",
            "transport": "sse",
        }
    }) as mcp_client:
        tools = mcp_client.get_tools()

        tax_tools = [
            t for t in tools
            if t.name in ["tax_calculator", "tax_saving_options"]
        ]

        system = f"""You are an expert Indian tax advisor for FY2024-25.

USER PROFILE:
{json.dumps(profile, indent=2)}

YOUR JOB — use tools step by step:
1. Run tax_calculator with regime="compare" to show old vs new regime
2. Run tax_saving_options to find what they are missing
3. Give clear recommendation

RESPONSE FORMAT:
- Show old regime tax vs new regime tax (exact ₹)
- Show how much they SAVE by choosing the better regime
- List top 3 actions they can take RIGHT NOW to save more tax
- Each action: what to do, how much to invest, how much tax saved

Keep under 300 words. Be specific with rupee amounts."""

        agent  = create_react_agent(llm, tax_tools)
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
