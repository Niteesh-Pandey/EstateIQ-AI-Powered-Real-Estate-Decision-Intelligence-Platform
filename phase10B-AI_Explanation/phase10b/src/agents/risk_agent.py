"""
Phase 9, Section 9.2 -- Risk Agent
======================================
"Calls Phase 7. It must use validated risk outputs." No risk math happens
here -- `monte_carlo.run_monte_carlo`, `risk_metrics.compute_risk_metrics`,
and `decision_stability.compute_decision_stability` are called directly,
byte-identical copies of the Phase 7 files. The `calibration_status =
UNCALIBRATED` tag Phase 7 always attaches is passed through unmodified --
this agent never upgrades or drops it.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "risk"))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "finance"))
from contracts import AgentFinding
from data_loader import load_property_financials_from_csv, load_property_financials_from_db
from engine import FinancialAssumptions
from monte_carlo import run_monte_carlo, MonteCarloConfig
from risk_metrics import compute_risk_metrics
from decision_stability import compute_decision_stability


def get_risk_analysis(property_id: int, source: str = "csv", n_simulations: int = 2000,
                       **assumption_overrides) -> AgentFinding:
    loader = load_property_financials_from_csv if source == "csv" else load_property_financials_from_db
    observed = loader(property_id)

    if observed.get("status") != "OK":
        return AgentFinding(
            agent_name="RiskAgent", status="INSUFFICIENT DATA", finding_type="risk_analysis",
            summary=f"No data available to simulate property {property_id}.",
            source="Phase 6 data_loader (via Phase 7)", confidence=0.0,
        )

    assumptions = FinancialAssumptions(property_id=property_id, **assumption_overrides)
    mc = run_monte_carlo(assumptions, observed, MonteCarloConfig(n_simulations=n_simulations, seed=42))

    if mc["status"] != "OK":
        return AgentFinding(
            agent_name="RiskAgent", status="INSUFFICIENT DATA", finding_type="risk_analysis",
            summary=f"Monte Carlo could not run for property {property_id}: {mc.get('reason')}",
            source="Phase 7 monte_carlo.run_monte_carlo (unchanged)", confidence=0.0,
            limitations=[mc.get("reason", "unknown")],
        )

    risk = compute_risk_metrics(mc)
    stability = compute_decision_stability(mc)

    summary = (f"Property {property_id}: {risk['probability_negative_npv']*100:.0f}% simulated probability "
               f"of negative NPV, {risk['probability_meets_target_irr']*100:.0f}% probability of meeting "
               f"the {risk['target_irr']*100:.0f}% target IRR. Base-case financial label "
               f"'{stability['base_case_label']}' held in {stability['stability_pct']:.0f}% of "
               f"{stability['n_simulations']:,} simulated draws.")

    return AgentFinding(
        agent_name="RiskAgent", status="UNCALIBRATED", finding_type="risk_analysis",
        # status intentionally UNCALIBRATED, not PASS -- Phase 7's calibration
        # status must survive into the agent layer unmodified (§7.7 / §9.6).
        summary=summary,
        metrics={
            "probability_negative_npv": risk["probability_negative_npv"],
            "probability_meets_target_irr": risk["probability_meets_target_irr"],
            "var_95_npv": risk["var_95_npv"],
            "cvar_95_npv": risk["cvar_95_npv"],
            "stability_pct": stability["stability_pct"],
            "base_case_label": stability["base_case_label"],
            "top_risk_driver": risk["risk_drivers_ranked"][0]["driver"] if risk["risk_drivers_ranked"] else None,
        },
        source="Phase 7 monte_carlo + risk_metrics + decision_stability (unchanged)",
        confidence=60.0,  # capped below "confident" tiers -- calibration_status is UNCALIBRATED (§7.7/§9.6)
        limitations=["Distributions are UNCALIBRATED (documented judgement-call bounds, not fitted to real "
                     "historical outcomes) -- see Phase 7 docs/limitations.md. Do not present these "
                     "probabilities as real-world probabilities."],
        raw={"monte_carlo_status": mc["status"], "risk_metrics": risk, "decision_stability": stability},
    )


if __name__ == "__main__":
    print(get_risk_analysis(1, annual_operating_expenses=180000, vacancy_rate=0.05,
                             appreciation_rate=0.08, n_simulations=1000).to_dict())
