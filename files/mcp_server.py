"""
MCP Tools Server
─────────────────
Runs as a separate process on port 8001.
Exposes all financial calculation tools to the agents.
Agents connect via SSE and call these tools in their ReAct loops.

Start with: python -m backend.tools.mcp_server
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("finance_tools")


# ─────────────────────────────────────────────
# FIRE / SIP TOOLS
# ─────────────────────────────────────────────

@mcp.tool()
def fire_corpus_calculator(
    monthly_expenses: float,
    current_age: int,
    target_retire_age: int,
    inflation_pct: float = 6.0,
) -> dict:
    """
    Calculate FIRE corpus needed and monthly SIP required.
    Uses 3.5% safe withdrawal rate (adjusted for India's inflation).

    Args:
        monthly_expenses: Current monthly expenses in rupees
        current_age: User's current age
        target_retire_age: Age they want to retire at
        inflation_pct: Expected annual inflation (default 6%)

    Returns:
        corpus_needed, expenses_at_retirement, monthly_sip_needed, years_to_retire
    """
    years = target_retire_age - current_age
    if years <= 0:
        return {"error": "Target retirement age must be greater than current age"}

    # Inflate expenses to retirement date
    annual_exp_now      = monthly_expenses * 12
    annual_exp_retire   = annual_exp_now * ((1 + inflation_pct / 100) ** years)

    # 3.5% SWR = 28.5x annual expenses (conservative for India)
    corpus_needed = annual_exp_retire / 0.035

    # Monthly SIP to reach corpus (assuming 12% equity return)
    r   = 0.12 / 12
    n   = years * 12
    sip = corpus_needed / ((((1 + r) ** n - 1) / r) * (1 + r))

    return {
        "corpus_needed":          round(corpus_needed),
        "expenses_at_retirement": round(annual_exp_retire / 12),
        "monthly_sip_needed":     round(sip),
        "years_to_retire":        years,
        "annual_exp_today":       round(annual_exp_now),
    }


@mcp.tool()
def sip_calculator(
    monthly_sip: float,
    annual_return_pct: float,
    years: int,
) -> dict:
    """
    Calculate future value of a monthly SIP investment.

    Args:
        monthly_sip: Monthly investment amount in rupees
        annual_return_pct: Expected annual return (e.g. 12 for 12%)
        years: Investment duration in years

    Returns:
        future_value, total_invested, wealth_gained
    """
    r  = (annual_return_pct / 100) / 12
    n  = years * 12
    fv = monthly_sip * (((1 + r) ** n - 1) / r) * (1 + r)

    return {
        "future_value":   round(fv),
        "total_invested": round(monthly_sip * n),
        "wealth_gained":  round(fv - (monthly_sip * n)),
        "return_multiple": round(fv / (monthly_sip * n), 2),
    }


# ─────────────────────────────────────────────
# TAX TOOLS
# ─────────────────────────────────────────────

@mcp.tool()
def tax_calculator(
    annual_income: float,
    regime: str = "compare",
    investments_80c: float = 0,
    nps_80ccd: float = 0,
    hra_exempt: float = 0,
    home_loan_interest: float = 0,
) -> dict:
    """
    Calculate income tax under old and new regime for India FY2024-25.

    Args:
        annual_income: Gross annual income in rupees
        regime: 'old', 'new', or 'compare'
        investments_80c: Total 80C investments (ELSS + PPF + ULIP etc, max 1.5L)
        nps_80ccd: NPS contribution under 80CCD(1B) (max 50k extra)
        hra_exempt: HRA exemption amount
        home_loan_interest: Home loan interest for 24(b) deduction (max 2L)

    Returns:
        Tax under requested regime(s) and recommendation if comparing
    """
    def _old(income, ded):
        std_ded  = 50_000
        taxable  = max(0, income - std_ded - ded)
        if taxable <= 250_000:   return 0.0
        if taxable <= 500_000:   return (taxable - 250_000) * 0.05
        if taxable <= 1_000_000: return 12_500 + (taxable - 500_000) * 0.20
        return 112_500 + (taxable - 1_000_000) * 0.30

    def _new(income):
        std_ded = 75_000
        taxable = max(0, income - std_ded)
        slabs = [
            (300_000,  0.00),
            (700_000,  0.05),
            (1_000_000, 0.10),
            (1_200_000, 0.15),
            (1_500_000, 0.20),
            (float("inf"), 0.30),
        ]
        tax, prev = 0.0, 0.0
        for limit, rate in slabs:
            if taxable <= prev:
                break
            tax  += (min(taxable, limit) - prev) * rate
            prev  = limit
        return tax

    def _add_cess(tax):
        return round(tax * 1.04, 2)    # 4% health & education cess

    deductions = (
        min(investments_80c,    150_000)
        + min(nps_80ccd,         50_000)
        + hra_exempt
        + min(home_loan_interest, 200_000)
    )

    result = {}

    if regime in ("old", "compare"):
        old_tax = _add_cess(_old(annual_income, deductions))
        result["old_regime"] = {
            "tax":            old_tax,
            "effective_rate": round((old_tax / annual_income) * 100, 1),
            "deductions_used": round(deductions),
            "in_hand_annual": round(annual_income - old_tax),
        }

    if regime in ("new", "compare"):
        new_tax = _add_cess(_new(annual_income))
        result["new_regime"] = {
            "tax":            new_tax,
            "effective_rate": round((new_tax / annual_income) * 100, 1),
            "in_hand_annual": round(annual_income - new_tax),
        }

    if regime == "compare":
        old_t = result["old_regime"]["tax"]
        new_t = result["new_regime"]["tax"]
        result["recommendation"] = "old" if old_t < new_t else "new"
        result["savings"]        = round(abs(old_t - new_t))
        result["verdict"]        = (
            f"{'Old' if old_t < new_t else 'New'} regime saves you "
            f"₹{round(abs(old_t - new_t)):,}/year"
        )

    return result


@mcp.tool()
def tax_saving_options(
    annual_income: float,
    already_invested_80c: float = 0,
    has_nps: bool = False,
    has_health_insurance: bool = False,
) -> dict:
    """
    Show all available tax saving options ranked by priority.

    Args:
        annual_income: Gross annual income in rupees
        already_invested_80c: Already invested under 80C this year
        has_nps: Whether user already has NPS account
        has_health_insurance: Whether user has health insurance

    Returns:
        List of tax saving options with amounts, sections, and tax impact
    """
    options    = []
    remaining_80c = max(0, 150_000 - already_invested_80c)

    if remaining_80c > 0:
        tax_rate = 0.30 if annual_income > 1_000_000 else 0.20 if annual_income > 500_000 else 0.05
        options.append({
            "option":        "ELSS Mutual Fund",
            "section":       "80C",
            "invest_amount": remaining_80c,
            "tax_saved":     round(remaining_80c * tax_rate),
            "lock_in":       "3 years (shortest in 80C)",
            "returns":       "12-14% historical",
            "priority":      1,
            "action":        f"Start SIP of ₹{round(remaining_80c/12):,}/month in any ELSS fund",
        })
        options.append({
            "option":        "PPF (Public Provident Fund)",
            "section":       "80C",
            "invest_amount": min(remaining_80c, 150_000),
            "tax_saved":     round(min(remaining_80c, 150_000) * tax_rate),
            "lock_in":       "15 years",
            "returns":       "7.1% tax-free",
            "priority":      2,
            "action":        "Open PPF account at any PSU bank or Post Office",
        })

    if not has_nps:
        nps_amount = 50_000
        tax_rate   = 0.30 if annual_income > 1_000_000 else 0.20
        options.append({
            "option":        "NPS Tier 1",
            "section":       "80CCD(1B) — OVER AND ABOVE 80C",
            "invest_amount": nps_amount,
            "tax_saved":     round(nps_amount * tax_rate),
            "lock_in":       "Till age 60",
            "returns":       "10-11% historical",
            "priority":      1,
            "action":        "Open NPS account at eNPS portal (enps.nsdl.com)",
        })

    if not has_health_insurance:
        options.append({
            "option":        "Health Insurance Premium",
            "section":       "80D",
            "invest_amount": 25_000,
            "tax_saved":     round(25_000 * 0.20),
            "lock_in":       "None — annual renewal",
            "returns":       "Health protection",
            "priority":      1,
            "action":        "Buy ₹10L family floater health policy",
        })

    total_additional_saving = sum(o["tax_saved"] for o in options)

    return {
        "options":                 options,
        "total_additional_saving": total_additional_saving,
        "message":                 f"You can save ₹{total_additional_saving:,} more in taxes this year",
    }


# ─────────────────────────────────────────────
# INSURANCE TOOLS
# ─────────────────────────────────────────────

@mcp.tool()
def insurance_checker(
    annual_income: float,
    age: int,
    has_term_insurance: bool = False,
    existing_term_cover: float = 0,
    has_health_insurance: bool = False,
    existing_health_cover: float = 0,
    dependents: int = 0,
) -> dict:
    """
    Check insurance adequacy and identify gaps.

    Args:
        annual_income: Annual income in rupees
        age: Current age
        has_term_insurance: Whether user has term insurance
        existing_term_cover: Existing term cover in rupees
        has_health_insurance: Whether user has health insurance
        existing_health_cover: Existing health cover in rupees
        dependents: Number of financial dependents

    Returns:
        Insurance gaps and recommendations with premium estimates
    """
    # Term insurance: 10-15x annual income recommended
    recommended_term  = annual_income * 12
    term_gap          = max(0, recommended_term - existing_term_cover)

    # Health insurance: ₹10L minimum, ₹20L for metros
    recommended_health = 1_000_000
    health_gap         = max(0, recommended_health - existing_health_cover)

    # Rough premium estimates (age-based)
    term_premium_est   = round((recommended_term / 1_000_000) * (age * 80)) if term_gap > 0 else 0
    health_premium_est = round(recommended_health * 0.005) if health_gap > 0 else 0     # ~0.5% of cover

    issues   = []
    actions  = []

    if term_gap > 0:
        issues.append(f"Term cover gap: ₹{term_gap:,.0f} (you need ₹{recommended_term:,.0f}, have ₹{existing_term_cover:,.0f})")
        actions.append({
            "action":   f"Buy ₹{recommended_term:,.0f} term plan",
            "premium":  f"~₹{term_premium_est:,}/year",
            "urgency":  "High — do this first",
        })

    if health_gap > 0:
        issues.append(f"Health cover gap: ₹{health_gap:,.0f}")
        actions.append({
            "action":   f"Buy ₹{recommended_health:,.0f} family floater health plan",
            "premium":  f"~₹{health_premium_est:,}/year",
            "urgency":  "High",
        })

    if not issues:
        issues = ["Insurance coverage looks adequate"]

    return {
        "issues":                  issues,
        "actions":                 actions,
        "recommended_term_cover":  recommended_term,
        "recommended_health_cover": recommended_health,
        "monthly_premium_budget":  round((term_premium_est + health_premium_est) / 12),
    }


# ─────────────────────────────────────────────
# MF ANALYSIS TOOLS
# ─────────────────────────────────────────────

@mcp.tool()
def calculate_xirr(
    investments: dict,
    assumed_return_pct: float = 12.0,
) -> dict:
    """
    Estimate portfolio XIRR based on current portfolio.
    (Simplified — real XIRR needs transaction history)

    Args:
        investments: Dict of {fund_name: current_value_in_rupees}
        assumed_return_pct: Base return assumption

    Returns:
        Estimated XIRR and portfolio breakdown
    """
    total = sum(investments.values())
    if total == 0:
        return {"error": "No investments found"}

    # Simple XIRR estimate — in real version use scipy.optimize
    xirr_estimate = assumed_return_pct - 1.5    # slight underperformance assumption

    return {
        "total_portfolio_value": round(total),
        "estimated_xirr":        round(xirr_estimate, 1),
        "fund_count":            len(investments),
        "breakdown":             {k: {"value": v, "pct": round(v/total*100, 1)} for k, v in investments.items()},
        "note":                  "Connect bank/CAMS for exact XIRR with transaction history",
    }


@mcp.tool()
def check_fund_overlap(fund_names: list) -> dict:
    """
    Check overlap between mutual funds (simplified using category overlap rules).

    Args:
        fund_names: List of mutual fund names

    Returns:
        Overlap analysis and recommendation
    """
    # Simplified overlap logic based on fund category keywords
    large_cap_keywords = ["large cap", "bluechip", "top 100", "nifty", "sensex", "flexi", "focused"]
    mid_cap_keywords   = ["mid cap", "midcap", "emerging"]

    large_cap_funds = [f for f in fund_names if any(kw in f.lower() for kw in large_cap_keywords)]
    mid_cap_funds   = [f for f in fund_names if any(kw in f.lower() for kw in mid_cap_keywords)]

    overlaps = []
    if len(large_cap_funds) > 1:
        overlaps.append({
            "funds":       large_cap_funds,
            "overlap_pct": 65,
            "issue":       "High overlap — these funds hold similar large-cap stocks",
            "action":      f"Keep one, exit others. Recommend keeping an index fund.",
        })

    return {
        "total_funds":  len(fund_names),
        "overlaps":     overlaps,
        "is_diversified": len(overlaps) == 0,
        "recommendation": "Consolidate to 3-4 funds maximum" if len(fund_names) > 4 else "Fund count is fine",
    }


@mcp.tool()
def benchmark_comparison(
    portfolio_xirr: float,
    benchmark: str = "Nifty50",
) -> dict:
    """
    Compare portfolio returns vs benchmark.

    Args:
        portfolio_xirr: Portfolio XIRR percentage
        benchmark: Benchmark name (default Nifty50)

    Returns:
        Comparison result and recommendation
    """
    benchmarks = {
        "Nifty50":    14.2,
        "Nifty500":   13.8,
        "SensexTRI":  13.9,
    }

    benchmark_return = benchmarks.get(benchmark, 14.2)
    alpha            = portfolio_xirr - benchmark_return

    return {
        "portfolio_xirr":    portfolio_xirr,
        "benchmark":         benchmark,
        "benchmark_return":  benchmark_return,
        "alpha":             round(alpha, 1),
        "verdict":           "Outperforming" if alpha > 0 else "Underperforming",
        "recommendation":    (
            "Great — your active funds are beating the index."
            if alpha > 1 else
            "Consider switching to Nifty50 index fund — lower cost, better returns."
        ),
    }


@mcp.tool()
def expense_ratio_checker(investments: dict) -> dict:
    """
    Estimate expense ratio drag on portfolio.

    Args:
        investments: Dict of {fund_name: current_value_in_rupees}

    Returns:
        Estimated annual cost and recommendation
    """
    total = sum(investments.values())

    # Estimate avg expense ratio (active ~1.5%, index ~0.1%)
    index_keywords = ["index", "nifty", "sensex", "etf"]
    index_value    = sum(v for k, v in investments.items() if any(kw in k.lower() for kw in index_keywords))
    active_value   = total - index_value

    annual_cost = (active_value * 0.015) + (index_value * 0.001)

    return {
        "total_portfolio":       round(total),
        "estimated_annual_cost": round(annual_cost),
        "avg_expense_ratio":     round(annual_cost / total * 100, 2) if total > 0 else 0,
        "active_funds_value":    round(active_value),
        "index_funds_value":     round(index_value),
        "recommendation": (
            f"You pay ~₹{round(annual_cost):,}/year in fund expenses. "
            + ("Shift more to index funds to reduce this." if active_value > index_value else "Good mix of index funds.")
        ),
    }


# ─────────────────────────────────────────────
# Run MCP server
# ─────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="sse", port=8001)
