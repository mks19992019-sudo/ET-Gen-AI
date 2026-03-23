"""
MF X-Ray Agent — ReAct agent for mutual fund portfolio analysis
────────────────────────────────────────────────────────────────
Tools: calculate_xirr, check_fund_overlap, benchmark_comparison, expense_ratio_checker
"""

import json
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from ..state import MoneyState

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)


async def mf_react_agent(state: MoneyState) -> dict:
    profile = state["profile"]

    async with MultiServerMCPClient({
        "finance_tools": {
            "url":       "http://localhost:8001/sse",
            "transport": "sse",
        }
    }) as mcp_client:
        tools = mcp_client.get_tools()

        mf_tools = [
            t for t in tools
            if t.name in [
                "calculate_xirr",
                "check_fund_overlap",
                "benchmark_comparison",
                "expense_ratio_checker",
            ]
        ]

        system = f"""You are a mutual fund portfolio analyst for India.

USER PORTFOLIO (from their profile):
{json.dumps(profile.get("investments", {}), indent=2)}

FULL PROFILE:
{json.dumps(profile, indent=2)}

YOUR JOB — use tools step by step:
1. calculate_xirr on their portfolio
2. check_fund_overlap to find redundant funds
3. benchmark_comparison vs Nifty50 TRI
4. expense_ratio_checker to find cost drag

RESPONSE FORMAT:
PORTFOLIO SUMMARY
Total invested: ₹X
Current value: ₹X (estimated)
XIRR: X.X%
Benchmark (Nifty50): X.X%
You are [outperforming/underperforming] by X.X%

ISSUES FOUND:
• [Issue 1 with specific fund names and numbers]
• [Issue 2]

REBALANCING PLAN:
• Exit: [fund name] — reason
• Add: [fund name] — reason
• Keep: [fund name] — reason

This saves you ₹X/year in fees and improves returns by ~X%"""

        agent  = create_react_agent(llm, mf_tools)
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
