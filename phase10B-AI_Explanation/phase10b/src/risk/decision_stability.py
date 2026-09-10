"""
Phase 7, Section 7.8 -- Decision Stability
=============================================
IMPORTANT SCOPE NOTE: the authoritative, deterministic DecisionPolicy
belongs to Phase 9 (Section 9.4) and combines market/prediction/financial/
risk/geo scores with explicit configurable weights. Phase 7 does not have
those other four scores yet (Phases 8/9 haven't run). The classification
rule below is a **minimal, clearly-scoped, financial-only** placeholder
used ONLY to answer Section 7.8's literal question -- "how often does a
decision change across simulated draws" -- for this financial dimension in
isolation. It must not be read as a preview of Phase 9's actual decision.

Rule (financial-only, documented, not the final DecisionPolicy):
  INVEST if IRR >= target_irr AND NPV > 0
  AVOID  if NPV < 0 AND IRR < 0
  HOLD   otherwise (a mixed/marginal outcome on this financial dimension)
"""


def classify_financial_outcome(irr, npv, target_irr) -> str:
    if irr is None:
        return "INSUFFICIENT"
    if irr >= target_irr and npv > 0:
        return "INVEST"
    if npv < 0 and irr < 0:
        return "AVOID"
    return "HOLD"


def compute_decision_stability(mc_result: dict) -> dict:
    if mc_result.get("status") != "OK":
        return {"status": "INSUFFICIENT DATA", "reason": mc_result.get("reason")}

    records = mc_result["records"]
    if not records:
        return {"status": "INSUFFICIENT DATA", "reason": "No valid simulation records."}

    target_irr = mc_result["target_irr"]
    counts = {"INVEST": 0, "HOLD": 0, "AVOID": 0, "INSUFFICIENT": 0}
    for r in records:
        label = classify_financial_outcome(r["irr"], r["npv"], target_irr)
        counts[label] += 1

    n = len(records)
    distribution = {k: round(100 * v / n, 1) for k, v in counts.items()}

    base = mc_result["base_result"]
    base_metrics = base.get("metrics") or {}
    base_label = classify_financial_outcome(base_metrics.get("irr"), base_metrics.get("npv"), target_irr)

    majority_label = max(counts, key=counts.get)
    stability_pct = distribution[majority_label]

    return {
        "status": "OK",
        "scope_note": "Financial dimension only -- NOT the Phase 9 authoritative DecisionPolicy. "
                      "See module docstring.",
        "base_case_label": base_label,
        "n_simulations": n,
        "decision_distribution_pct": distribution,
        "majority_label": majority_label,
        "stability_pct": stability_pct,
        "unstable": base_label != majority_label,
    }


if __name__ == "__main__":
    import json
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "finance"))
    from data_loader import load_property_financials_from_csv
    from engine import FinancialAssumptions
    from monte_carlo import run_monte_carlo, MonteCarloConfig

    observed = load_property_financials_from_csv(1)
    base = FinancialAssumptions(property_id=1, annual_operating_expenses=180000,
                                 vacancy_rate=0.05, appreciation_rate=0.08)
    mc = run_monte_carlo(base, observed, MonteCarloConfig(n_simulations=1000))
    print(json.dumps(compute_decision_stability(mc), indent=2, default=str))
