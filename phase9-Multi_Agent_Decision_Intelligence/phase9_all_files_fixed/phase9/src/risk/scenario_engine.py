"""
Phase 7, Section 7.6 -- Scenarios (Base / Downside / Severe Downside / Upside)
==================================================================================
Reuses Phase 6's `scenarios.run_financial_engine` and its Base/Upside/
Downside shocks unchanged, and adds one additional documented stress point:
Severe Downside. As with Phase 6's SCENARIO_SHOCKS, this magnitude is an
ASSUMED stress point, not a calibrated probability -- consistent with this
phase's overall UNCALIBRATED status (Section 7.7).
"""
import os
import sys
from dataclasses import replace


_HERE = os.path.abspath('')
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "finance"))
from engine import run_financial_engine  # noqa: E402
from scenarios import run_scenarios as run_base_scenarios  # noqa: E402

SEVERE_DOWNSIDE_SHOCK = {"appreciation_delta": -0.10, "vacancy_multiplier": 3.0, "opex_multiplier": 1.20}


def run_extended_scenarios(base_assumptions, observed: dict) -> dict:
    base_three = run_base_scenarios(base_assumptions, observed)
    results = dict(base_three)

    if base_three["Base"]["validation_status"] == "INSUFFICIENT DATA":
        results["Severe Downside"] = {"validation_status": "INSUFFICIENT DATA",
                                       "reason": "Base scenario is INSUFFICIENT DATA; severe stress not "
                                                 "applied to an undefined baseline."}
        return results

    resolved = base_three["Base"]["assumptions_used"]
    shocked = replace(
        base_assumptions,
        appreciation_rate=(resolved["appreciation_rate"] + SEVERE_DOWNSIDE_SHOCK["appreciation_delta"])
            if resolved["appreciation_rate"] is not None else None,
        vacancy_rate=min(1.0, resolved["vacancy_rate"] * SEVERE_DOWNSIDE_SHOCK["vacancy_multiplier"]),
        annual_operating_expenses=(resolved["annual_operating_expenses"] * SEVERE_DOWNSIDE_SHOCK["opex_multiplier"])
            if resolved["annual_operating_expenses"] is not None else None,
    )
    results["Severe Downside"] = run_financial_engine(shocked, observed)
    return results


def extended_scenario_summary(results: dict) -> list:
    rows = []
    for name in ("Severe Downside", "Downside", "Base", "Upside"):
        r = results.get(name, {})
        m = r.get("metrics") or {}
        rows.append({
            "scenario": name,
            "validation_status": r.get("validation_status"),
            "irr": m.get("irr"),
            "npv": m.get("npv"),
            "roi_total_holding_period": m.get("roi_total_holding_period"),
        })
    return rows


if __name__ == "__main__":
    import json
    sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "finance"))
    from data_loader import load_property_financials_from_csv
    from engine import FinancialAssumptions

    observed = load_property_financials_from_csv(1)
    base = FinancialAssumptions(property_id=1, annual_operating_expenses=180000,
                                 vacancy_rate=0.05, appreciation_rate=0.08)
    results = run_extended_scenarios(base, observed)
    print(json.dumps(extended_scenario_summary(results), indent=2, default=str))

