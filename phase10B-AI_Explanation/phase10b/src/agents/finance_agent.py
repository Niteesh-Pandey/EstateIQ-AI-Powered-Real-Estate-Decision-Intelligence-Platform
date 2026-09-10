"""
Phase 9, Section 9.2 -- Finance Agent
=========================================
"Calls the deterministic Phase 6 financial engine. It must not calculate
financial metrics through LLM reasoning." This agent calls
`engine.run_financial_engine()` and `scenarios.run_scenarios()` directly --
byte-identical copies of the Phase 6 files -- and does no arithmetic itself.

If the Prediction Agent produced a valuation (PASS WITH LIMITATIONS tier),
this agent can optionally use it as the ASSUMED `purchase_price` instead of
`asking_price` -- but only when the caller explicitly opts in
(`use_predicted_valuation=True`), never silently, since asking price vs. a
model's fair-value estimate are different facts a caller should choose
between deliberately (same reasoning Phase 6 documented for not
auto-substituting a past transaction price for asking price).
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "finance"))
from contracts import AgentFinding
from data_loader import load_property_financials_from_csv, load_property_financials_from_db
from engine import FinancialAssumptions, FinancingTerms, run_financial_engine
from scenarios import run_scenarios, scenario_summary


def get_financials(property_id: int, source: str = "csv", predicted_valuation: float = None,
                    use_predicted_valuation: bool = False, **assumption_overrides) -> AgentFinding:
    loader = load_property_financials_from_csv if source == "csv" else load_property_financials_from_db
    observed = loader(property_id)

    if observed.get("status") != "OK":
        return AgentFinding(
            agent_name="FinanceAgent", status="INSUFFICIENT DATA", finding_type="financial_analysis",
            summary=f"No financial data available for property {property_id}.",
            source="Phase 6 data_loader", confidence=0.0,
            limitations=[observed.get("reason", "unknown")],
        )

    kwargs = dict(property_id=property_id)
    if use_predicted_valuation and predicted_valuation:
        kwargs["purchase_price"] = predicted_valuation
    kwargs.update(assumption_overrides)
    assumptions = FinancialAssumptions(**kwargs)

    result = run_financial_engine(assumptions, observed)
    scenarios = run_scenarios(assumptions, observed)
    scen_summary = scenario_summary(scenarios)

    if result["validation_status"] == "INSUFFICIENT DATA":
        return AgentFinding(
            agent_name="FinanceAgent", status="INSUFFICIENT DATA", finding_type="financial_analysis",
            summary=f"Property {property_id}: financial engine could not resolve required inputs.",
            source="Phase 6 engine.run_financial_engine (unchanged)", confidence=0.0,
            limitations=result.get("insufficient_data_fields", []),
            raw=result,
        )

    m = result["metrics"]
    summary = (f"Property {property_id}: cap rate {m['cap_rate']*100:.2f}%, IRR "
               f"{m['irr']*100:.2f}% (5-yr Base case), NPV ₹{m['npv']:,.0f} at "
               f"{result['assumptions_used']['discount_rate']*100:.0f}% discount rate.")

    status = "PASS" if result["validation_status"] == "PASS" else "PASS WITH LIMITATIONS"
    confidence = 85.0 if status == "PASS" else 60.0

    return AgentFinding(
        agent_name="FinanceAgent", status=status, finding_type="financial_analysis",
        summary=summary,
        metrics=m,
        source="Phase 6 engine.run_financial_engine + scenarios.run_scenarios (unchanged)",
        confidence=confidence,
        limitations=result.get("limitations", []),
        raw={"base_result": result, "scenario_summary": scen_summary},
    )


if __name__ == "__main__":
    print(get_financials(1, annual_operating_expenses=180000, vacancy_rate=0.05,
                          appreciation_rate=0.08).to_dict())
