"""
Clarifier Node
───────────────
Asks for ONE missing field at a time.
Never bombards user with multiple questions.
Triggered by edges.py when profile is missing critical info.
"""

from ..state import MoneyState

# Human-friendly questions for each field
QUESTIONS = {
    "age":       "To give you accurate advice — how old are you currently?",
    "income":    "What is your annual income (gross, in ₹)? You can say something like '18 lakh' or '₹1.5L/month'.",
    "expenses":  "Roughly what are your monthly expenses? (rent, food, EMIs, subscriptions — everything)",
    "risk":      "How would you describe your risk appetite?\n• Conservative (safety first)\n• Moderate (balanced growth)\n• Aggressive (maximum growth, okay with volatility)",
    "investments": "Do you have any existing investments? (MF, PPF, FD, stocks — anything) Even rough amounts help.",
    "insurance": "Do you have a term life insurance policy? And health insurance?",
}

DEFAULT_QUESTION = "Could you share a bit more about your financial situation so I can give you accurate advice?"


async def clarifier_node(state: MoneyState) -> dict:
    missing = state.get("missing_field")
    question = QUESTIONS.get(missing, DEFAULT_QUESTION)

    return {
        "messages":     [{"role": "assistant", "content": question}],
        "final_output": {"text": question, "chart_data": {}, "cards": []},
    }
