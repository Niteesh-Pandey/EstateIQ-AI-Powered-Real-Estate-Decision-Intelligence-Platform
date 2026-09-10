"""
Phase 6, Section 6.3/6.4 -- Deterministic Financial Engine
=============================================================
Every calculation here is plain arithmetic -- no LLM, no ML model (Master
Prompt Section 3.4: ROI/IRR/NPV/NOI/yield/DSCR must be deterministic code).
Given the same FinancialAssumptions, this module always returns the exact
same FinancialResult.

Governance (Section 13): every number in the output is tagged
  OBSERVED  -- taken directly from Phase 1 data (data_loader.py)
  ASSUMED   -- supplied or defaulted by the caller (never invented silently;
               every default used is listed in `assumptions_used` with its
               source)
  DERIVED   -- computed from OBSERVED/ASSUMED inputs by this engine

Missing Input Policy (Section 6.7): if a value required for a metric is not
available (neither OBSERVED nor ASSUMED), that metric is set to None and the
result's `insufficient_data_fields` lists exactly which input was missing --
never a guessed number.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional


# ---------------------------------------------------------------- defaults
# Every default below is an explicit, documented ASSUMPTION a caller may
# override -- not a value inferred from data. Listed in one place so a
# reviewer can audit every silent default this engine is capable of using.
DEFAULT_HOLDING_PERIOD_YEARS = 5.0          # common institutional hold convention
DEFAULT_DISCOUNT_RATE = 0.10                # typical unlevered required-return benchmark, India resi
DEFAULT_CLOSING_COST_PCT = 0.07             # India: stamp duty + registration + misc., typical 5-8%
DEFAULT_SELLING_COST_PCT = 0.02             # typical brokerage on exit
DEFAULT_DOWN_PAYMENT_PCT = 1.0              # default = unlevered / all-cash (safest default; leverage
                                             # must be explicitly opted into, never assumed)
DEFAULT_OTHER_INCOME_ANNUAL = 0.0           # no other income unless caller states one


@dataclass
class FinancingTerms:
    down_payment_pct: float = DEFAULT_DOWN_PAYMENT_PCT   # 1.0 = all-cash
    loan_interest_rate: Optional[float] = None            # required if down_payment_pct < 1.0
    loan_term_years: Optional[float] = None                # required if down_payment_pct < 1.0


@dataclass
class FinancialAssumptions:
    property_id: int
    purchase_price: Optional[float] = None      # None => use OBSERVED asking_price
    monthly_rent: Optional[float] = None        # None => use OBSERVED monthly_rent_listed
    vacancy_rate: Optional[float] = None        # None => use OBSERVED (if reliable), else INSUFFICIENT DATA
    annual_operating_expenses: Optional[float] = None  # None => use OBSERVED (if available)
    other_income_annual: float = DEFAULT_OTHER_INCOME_ANNUAL
    holding_period_years: float = DEFAULT_HOLDING_PERIOD_YEARS
    appreciation_rate: Optional[float] = None   # None => use OBSERVED locality CAGR (if reliable)
    exit_cap_rate: Optional[float] = None        # if set, overrides appreciation-based exit value
    discount_rate: float = DEFAULT_DISCOUNT_RATE
    closing_cost_pct: float = DEFAULT_CLOSING_COST_PCT
    selling_cost_pct: float = DEFAULT_SELLING_COST_PCT
    financing: FinancingTerms = field(default_factory=FinancingTerms)


def resolve_inputs(assumptions: FinancialAssumptions, observed: dict) -> dict:
    """Merges caller assumptions with OBSERVED facts. Applies the Missing
    Input Policy: nothing is guessed. Returns a dict of resolved values plus
    `governance` tags and `insufficient_data_fields`."""
    gov = {}
    insufficient = []

    def pick(assumed_val, observed_val, key, required=True):
        if assumed_val is not None:
            gov[key] = "ASSUMED"
            return assumed_val
        if observed_val is not None:
            gov[key] = "OBSERVED"
            return observed_val
        gov[key] = "INSUFFICIENT DATA"
        if required:
            insufficient.append(key)
        return None

    purchase_price = pick(assumptions.purchase_price,
                           observed.get("property_facts", {}).get("asking_price"),
                           "purchase_price")
    monthly_rent = pick(assumptions.monthly_rent,
                         observed.get("property_facts", {}).get("monthly_rent_listed"),
                         "monthly_rent")
    vacancy_rate = pick(assumptions.vacancy_rate,
                         observed.get("observed_vacancy_rate"),
                         "vacancy_rate", required=False)
    if vacancy_rate is None:
        gov["vacancy_rate"] = "ASSUMED_DEFAULT"
        vacancy_rate = 0.0  # documented conservative-but-explicit default: "no vacancy assumed"
        insufficient.append("vacancy_rate (defaulted to 0.0 -- no property-level or caller vacancy data)")

    opex_block = observed.get("observed_annual_operating_expenses")
    observed_opex = opex_block["total"] if opex_block else None
    annual_opex = pick(assumptions.annual_operating_expenses, observed_opex,
                        "annual_operating_expenses", required=False)
    if annual_opex is None:
        gov["annual_operating_expenses"] = "INSUFFICIENT DATA"
        insufficient.append("annual_operating_expenses")

    appreciation_block = observed.get("observed_locality_appreciation", {})
    observed_appreciation = appreciation_block.get("annualized_growth_rate") \
        if appreciation_block.get("reliable_for_use_as_default") else None
    appreciation_rate = pick(assumptions.appreciation_rate, observed_appreciation,
                              "appreciation_rate", required=False)
    if appreciation_rate is None:
        gov["appreciation_rate"] = "INSUFFICIENT DATA"
        note = "appreciation_rate"
        if appreciation_block.get("status") == "OBSERVED_BUT_UNRELIABLE":
            note += " (locality historical CAGR exists but is flagged unreliable -- see data_loader)"
        insufficient.append(note)

    return {
        "purchase_price": purchase_price,
        "monthly_rent": monthly_rent,
        "vacancy_rate": vacancy_rate,
        "annual_operating_expenses": annual_opex,
        "other_income_annual": assumptions.other_income_annual,
        "holding_period_years": assumptions.holding_period_years,
        "appreciation_rate": appreciation_rate,
        "exit_cap_rate": assumptions.exit_cap_rate,
        "discount_rate": assumptions.discount_rate,
        "closing_cost_pct": assumptions.closing_cost_pct,
        "selling_cost_pct": assumptions.selling_cost_pct,
        "financing": assumptions.financing,
        "governance": gov,
        "insufficient_data_fields": insufficient,
    }


# ------------------------------------------------------------- core math
def annual_debt_service(loan_amount: float, annual_rate: float, term_years: float) -> float:
    if loan_amount <= 0:
        return 0.0
    if annual_rate <= 0:
        return loan_amount / term_years
    r = annual_rate
    n = term_years
    return loan_amount * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


def compute_cash_flows(resolved: dict) -> Optional[dict]:
    """Builds the full year-by-year cash flow schedule. Returns None (with
    the reason left to the caller via insufficient_data_fields) if a
    required input is missing."""
    required = ["purchase_price", "monthly_rent", "annual_operating_expenses", "holding_period_years"]
    if any(resolved.get(k) is None for k in required):
        return None

    purchase_price = resolved["purchase_price"]
    gross_annual_rent = resolved["monthly_rent"] * 12
    vacancy_rate = resolved["vacancy_rate"]
    egi = gross_annual_rent * (1 - vacancy_rate) + resolved["other_income_annual"]
    opex = resolved["annual_operating_expenses"]
    noi = egi - opex
    holding_years = int(round(resolved["holding_period_years"]))

    fin = resolved["financing"]
    down_pct = fin.down_payment_pct
    loan_amount = purchase_price * (1 - down_pct)
    debt_service = 0.0
    if loan_amount > 0:
        if fin.loan_interest_rate is None or fin.loan_term_years is None:
            return None  # financing selected but terms missing -- do not guess a rate
        debt_service = annual_debt_service(loan_amount, fin.loan_interest_rate, fin.loan_term_years)

    closing_costs = purchase_price * resolved["closing_cost_pct"]
    equity_invested = purchase_price * down_pct + closing_costs

    # Exit value: prefer exit cap rate (NOI / cap rate) if supplied, else
    # appreciation-compounded price. Both require a real input -- no default
    # exit value is ever fabricated.
    exit_value = None
    if resolved.get("exit_cap_rate"):
        exit_value = noi / resolved["exit_cap_rate"]
    elif resolved.get("appreciation_rate") is not None:
        exit_value = purchase_price * (1 + resolved["appreciation_rate"]) ** holding_years

    remaining_loan_balance = _remaining_balance(loan_amount, fin.loan_interest_rate,
                                                 fin.loan_term_years, holding_years) if loan_amount > 0 else 0.0
    selling_costs = (exit_value or 0.0) * resolved["selling_cost_pct"]
    net_sale_proceeds = None
    if exit_value is not None:
        net_sale_proceeds = exit_value - selling_costs - remaining_loan_balance

    annual_net_cash_flow = noi - debt_service
    schedule = [-equity_invested] + [annual_net_cash_flow] * holding_years
    if net_sale_proceeds is not None:
        schedule[-1] += net_sale_proceeds

    return {
        "gross_annual_rent": round(gross_annual_rent, 2),
        "effective_gross_income": round(egi, 2),
        "annual_operating_expenses": round(opex, 2),
        "noi": round(noi, 2),
        "loan_amount": round(loan_amount, 2),
        "annual_debt_service": round(debt_service, 2),
        "closing_costs": round(closing_costs, 2),
        "equity_invested": round(equity_invested, 2),
        "annual_net_cash_flow": round(annual_net_cash_flow, 2),
        "exit_value": round(exit_value, 2) if exit_value is not None else None,
        "remaining_loan_balance_at_exit": round(remaining_loan_balance, 2),
        "selling_costs": round(selling_costs, 2),
        "net_sale_proceeds": round(net_sale_proceeds, 2) if net_sale_proceeds is not None else None,
        "holding_period_years": holding_years,
        "cash_flow_schedule": [round(c, 2) for c in schedule],
    }


def _remaining_balance(loan_amount, annual_rate, term_years, years_elapsed) -> float:
    if loan_amount <= 0:
        return 0.0
    if years_elapsed >= term_years:
        return 0.0
    if annual_rate <= 0:
        return loan_amount * max(0.0, (term_years - years_elapsed) / term_years)
    payment = annual_debt_service(loan_amount, annual_rate, term_years)
    balance = loan_amount
    for _ in range(years_elapsed):
        interest = balance * annual_rate
        principal = payment - interest
        balance -= principal
    return max(0.0, balance)


# ------------------------------------------------------------- metrics
def npv(cash_flows: list, discount_rate: float) -> float:
    return sum(cf / (1 + discount_rate) ** t for t, cf in enumerate(cash_flows))


def irr(cash_flows: list, tol: float = 1e-6, max_iter: int = 200) -> Optional[float]:
    """Bisection search for the discount rate where NPV = 0. Returns None if
    no sign change exists in the cash flow series (IRR undefined -- e.g. all
    outflows, or all inflows), rather than returning a meaningless number."""
    if not cash_flows or cash_flows[0] >= 0 or all(cf <= 0 for cf in cash_flows[1:]):
        return None
    lo, hi = -0.99, 10.0
    f_lo, f_hi = npv(cash_flows, lo), npv(cash_flows, hi)
    if f_lo * f_hi > 0:
        return None  # no sign change in the search range -- IRR not found, not invented
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        f_mid = npv(cash_flows, mid)
        if abs(f_mid) < tol:
            return round(mid, 4)
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return round((lo + hi) / 2, 4)


def payback_period(cash_flows: list) -> Optional[float]:
    cumulative = 0.0
    for t, cf in enumerate(cash_flows):
        prev_cumulative = cumulative
        cumulative += cf
        if cumulative >= 0 and t > 0:
            frac = -prev_cumulative / cf if cf != 0 else 0
            return round(t - 1 + frac, 2)
    return None  # never recovers within the holding period -- not a guessable number


def compute_metrics(resolved: dict, cf: dict) -> dict:
    purchase_price = resolved["purchase_price"]
    noi = cf["noi"]
    gross_yield = cf["gross_annual_rent"] / purchase_price if purchase_price else None
    net_yield = noi / purchase_price if purchase_price else None
    cap_rate = net_yield  # at acquisition, cap rate == net yield on purchase price
    cash_on_cash = (cf["annual_net_cash_flow"] / cf["equity_invested"]) if cf["equity_invested"] else None
    dscr = (noi / cf["annual_debt_service"]) if cf["annual_debt_service"] > 0 else None

    schedule = cf["cash_flow_schedule"]
    metric_irr = irr(schedule)
    metric_npv = npv(schedule, resolved["discount_rate"])
    metric_payback = payback_period(schedule)

    # ROI (total, over the full holding period) = NET profit / equity invested,
    # i.e. (total cash received - equity invested) / equity invested. This was
    # previously computed as total_return / equity_invested (a cash MULTIPLE,
    # not a return) -- fixed after audit found it overstated ROI by exactly
    # 100 percentage points (e.g. a true 10% single-period return was reported
    # as 110%). See docs/limitations.md for the audit note.
    total_return = sum(schedule[1:]) if len(schedule) > 1 else None
    roi = ((total_return - cf["equity_invested"]) / cf["equity_invested"]) \
        if cf["equity_invested"] and total_return is not None else None

    cagr = None
    if cf.get("exit_value") is not None and purchase_price:
        years = cf["holding_period_years"]
        if years > 0 and cf["exit_value"] > 0 and purchase_price > 0:
            cagr = round((cf["exit_value"] / purchase_price) ** (1 / years) - 1, 4)

    return {
        "gross_yield": round(gross_yield, 4) if gross_yield is not None else None,
        "net_yield": round(net_yield, 4) if net_yield is not None else None,
        "cap_rate": round(cap_rate, 4) if cap_rate is not None else None,
        "cash_on_cash_return": round(cash_on_cash, 4) if cash_on_cash is not None else None,
        "dscr": round(dscr, 2) if dscr is not None else None,
        "roi_total_holding_period": round(roi, 4) if roi is not None else None,
        "irr": metric_irr,
        "npv": round(metric_npv, 2),
        "payback_period_years": metric_payback,
        "terminal_value_cagr": cagr,
    }


def run_financial_engine(assumptions: FinancialAssumptions, observed: dict) -> dict:
    """Top-level entry point -- Section 6.8's FinancialResult contract."""
    resolved = resolve_inputs(assumptions, observed)
    cf = compute_cash_flows(resolved)

    if cf is None:
        return {
            "property_id": assumptions.property_id,
            "validation_status": "INSUFFICIENT DATA",
            "assumptions_used": _serializable(resolved),
            "cash_flows": None,
            "metrics": None,
            "insufficient_data_fields": resolved["insufficient_data_fields"] or
                ["financing terms incomplete (loan_interest_rate / loan_term_years) while leveraged"],
            "limitations": ["One or more required inputs were unavailable; no value was guessed. "
                             "See insufficient_data_fields."],
        }

    metrics = compute_metrics(resolved, cf)
    status = "PASS WITH LIMITATIONS" if resolved["insufficient_data_fields"] else "PASS"

    return {
        "property_id": assumptions.property_id,
        "validation_status": status,
        "assumptions_used": _serializable(resolved),
        "cash_flows": cf,
        "metrics": metrics,
        "insufficient_data_fields": resolved["insufficient_data_fields"],
        "limitations": _limitations(resolved, cf, metrics),
    }


def _limitations(resolved, cf, metrics) -> list:
    notes = []
    if resolved["governance"].get("vacancy_rate") == "ASSUMED_DEFAULT":
        notes.append("No property-level or caller-supplied vacancy data -- vacancy_rate defaulted to 0.0 "
                      "(best case). Treat yield/cash-flow figures as an upper bound until real vacancy "
                      "data or an explicit assumption is supplied.")
    if resolved["governance"].get("annual_operating_expenses") == "INSUFFICIENT DATA":
        notes.append("No expense records for this property and none supplied -- NOI/yield/cap rate could "
                      "not be computed.")
    if metrics and metrics.get("irr") is None:
        notes.append("IRR undefined for this cash flow series (no sign change found) -- reported as None, "
                      "not a fabricated number.")
    if cf and cf.get("exit_value") is None:
        notes.append("No appreciation_rate or exit_cap_rate available -- exit value, terminal CAGR, and "
                      "net sale proceeds could not be computed.")
    return notes


def _serializable(resolved: dict) -> dict:
    out = dict(resolved)
    out["financing"] = asdict(out["financing"])
    return out


if __name__ == "__main__":
    import json
    import sys
    sys.path.insert(0, ".")
    from data_loader import load_property_financials_from_csv

    observed = load_property_financials_from_csv(1)
    assumptions = FinancialAssumptions(property_id=1, annual_operating_expenses=180000,
                                        vacancy_rate=0.05, appreciation_rate=0.08)
    result = run_financial_engine(assumptions, observed)
    print(json.dumps(result, indent=2, default=str))
