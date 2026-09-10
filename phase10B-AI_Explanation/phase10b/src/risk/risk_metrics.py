"""
Phase 7, Section 7.5 -- Risk Metrics
=======================================
All metrics computed directly from the Monte Carlo records produced by
`monte_carlo.run_monte_carlo()`. Nothing here re-derives financial figures --
it only summarizes the distribution the simulation already produced
(Section 7.2's "do not duplicate financial calculations" applies here too:
these are statistics of existing outputs, not new financial math).
"""
import numpy as np


def compute_risk_metrics(mc_result: dict) -> dict:
    if mc_result.get("status") != "OK":
        return {"status": "INSUFFICIENT DATA", "reason": mc_result.get("reason")}

    records = mc_result["records"]
    if not records:
        return {"status": "INSUFFICIENT DATA", "reason": "No valid simulation records to summarize."}

    irrs = np.array([r["irr"] for r in records if r["irr"] is not None])
    npvs = np.array([r["npv"] for r in records])
    rois = np.array([r["roi"] for r in records if r["roi"] is not None])
    target_irr = mc_result["target_irr"]

    n_irr_undefined = len(records) - len(irrs)  # sample-level IRR: None when no sign change

    def percentiles(arr):
        return {f"p{p}": round(float(np.percentile(arr, p)), 4) for p in (5, 10, 25, 50, 75, 90, 95)}

    # VaR_95 / CVaR_95 on NPV: the loss level not expected to be exceeded
    # with 95% confidence, and the average loss in the worst 5% of draws.
    # Reported as the raw (usually negative) NPV values themselves, not as
    # a separately-signed "loss amount", to avoid a sign-convention bug --
    # a reader should read "VaR_95 = -₹2.1M" as "5% of simulated outcomes
    # are at or below -₹2.1M NPV".
    var_95_npv = float(np.percentile(npvs, 5))
    cvar_95_npv = float(npvs[npvs <= var_95_npv].mean()) if (npvs <= var_95_npv).any() else var_95_npv
    var_90_npv = float(np.percentile(npvs, 10))
    cvar_90_npv = float(npvs[npvs <= var_90_npv].mean()) if (npvs <= var_90_npv).any() else var_90_npv

    prob_negative_npv = float((npvs < 0).mean())
    prob_negative_irr = float((irrs < 0).mean()) if len(irrs) else None
    prob_target_irr = float((irrs >= target_irr).mean()) if len(irrs) else None

    # --- Risk drivers: Pearson correlation of each sampled input with IRR
    # outcome, computed on the simulation's own draws. This ranks which
    # input the simulated outcome is most sensitive to; it is a diagnostic
    # of THIS simulation, not an externally-validated causal estimate.
    drivers = {}
    input_keys = ["sampled_purchase_price", "sampled_vacancy_rate", "sampled_opex", "sampled_appreciation"]
    for key in input_keys:
        vals = np.array([r[key] for r in records if r[key] is not None and r["irr"] is not None])
        matched_irr = np.array([r["irr"] for r in records if r[key] is not None and r["irr"] is not None])
        if len(vals) > 10 and np.std(vals) > 0:
            drivers[key.replace("sampled_", "")] = round(float(np.corrcoef(vals, matched_irr)[0, 1]), 3)
        else:
            drivers[key.replace("sampled_", "")] = None
    ranked_drivers = sorted(
        [(k, v) for k, v in drivers.items() if v is not None],
        key=lambda kv: abs(kv[1]), reverse=True
    )

    return {
        "status": "OK",
        "calibration_status": mc_result["calibration_status"],
        "n_simulations_valid": mc_result["n_simulations_valid"],
        "n_simulations_insufficient_data": mc_result["n_simulations_insufficient_data"],
        "n_irr_undefined_in_valid_draws": int(n_irr_undefined),
        "target_irr": round(target_irr, 4),
        "irr_distribution": {
            "mean": round(float(irrs.mean()), 4) if len(irrs) else None,
            "std": round(float(irrs.std()), 4) if len(irrs) else None,
            **({"percentiles": percentiles(irrs)} if len(irrs) else {}),
        },
        "npv_distribution": {
            "mean": round(float(npvs.mean()), 2),
            "std": round(float(npvs.std()), 2),
            "percentiles": {k: round(v, 2) for k, v in percentiles(npvs).items()},
        },
        "roi_distribution": {
            "mean": round(float(rois.mean()), 4) if len(rois) else None,
            "std": round(float(rois.std()), 4) if len(rois) else None,
        },
        "probability_negative_npv": round(prob_negative_npv, 4),
        "probability_negative_irr": round(prob_negative_irr, 4) if prob_negative_irr is not None else None,
        "probability_meets_target_irr": round(prob_target_irr, 4) if prob_target_irr is not None else None,
        "var_95_npv": round(var_95_npv, 2),
        "cvar_95_npv": round(cvar_95_npv, 2),
        "var_90_npv": round(var_90_npv, 2),
        "cvar_90_npv": round(cvar_90_npv, 2),
        "risk_drivers_ranked": [{"driver": k, "correlation_with_irr": v} for k, v in ranked_drivers],
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
    risk = compute_risk_metrics(mc)
    print(json.dumps(risk, indent=2, default=str))
