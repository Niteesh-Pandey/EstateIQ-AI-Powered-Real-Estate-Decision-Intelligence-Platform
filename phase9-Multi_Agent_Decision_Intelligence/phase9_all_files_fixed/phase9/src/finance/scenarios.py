#!/usr/bin/env python
# coding: utf-8

# In[1]:


"""
Phase 6, Section 6.5/6.6 -- Scenarios & Sensitivity Analysis
================================================================
Both reuse `engine.run_financial_engine` unchanged -- scenarios/sensitivity
are just different FinancialAssumptions fed through the same deterministic
math (Master Prompt Section 3.4: no duplicated calculation logic).

Scenario shifts (Section 6.5) are documented, symmetric-ish percentage
adjustments to price-sensitive drivers -- explicitly ASSUMED stress
magnitudes, not derived from data (no historical volatility model exists
in this dataset to derive them from; stated plainly here rather than
implied to be empirically calibrated).
"""
import copy
from dataclasses import replace

from engine import FinancialAssumptions, run_financial_engine

# Documented, symmetric stress magnitudes applied to the Base case's
# resolved vacancy_rate, appreciation_rate and annual_operating_expenses.
# These are ASSUMED scenario shocks (Section 6.5), not calibrated to any
# historical distribution -- Phase 7's Monte Carlo engine is where a
# calibrated/uncalibrated distribution belongs (Section 7.7). Do not read
# these three scenario points as probabilities of anything.
SCENARIO_SHOCKS = {
    "Upside": {"appreciation_delta": +0.03, "vacancy_multiplier": 0.5, "opex_multiplier": 0.95},
    "Base": {"appreciation_delta": 0.0, "vacancy_multiplier": 1.0, "opex_multiplier": 1.0},
    "Downside": {"appreciation_delta": -0.05, "vacancy_multiplier": 2.0, "opex_multiplier": 1.10},
}


def run_scenarios(base_assumptions: FinancialAssumptions, observed: dict) -> dict:
    """Runs Base first to resolve OBSERVED/ASSUMED inputs once, then applies
    each scenario's documented shock on top of that resolved starting point.
    If Base itself is INSUFFICIENT DATA, Upside/Downside are not run --
    stressing an undefined baseline produces a meaningless number, not a
    more informative one."""
    base_result = run_financial_engine(base_assumptions, observed)
    results = {"Base": base_result}

    if base_result["validation_status"] == "INSUFFICIENT DATA":
        results["Upside"] = {"validation_status": "INSUFFICIENT DATA",
                              "reason": "Base scenario is INSUFFICIENT DATA; scenario stress not applied "
                                        "to an undefined baseline."}
        results["Downside"] = results["Upside"]
        return results

    resolved = base_result["assumptions_used"]
    for name in ("Upside", "Downside"):
        shock = SCENARIO_SHOCKS[name]
        shocked = replace(
            base_assumptions,
            appreciation_rate=(resolved["appreciation_rate"] + shock["appreciation_delta"])
                if resolved["appreciation_rate"] is not None else None,
            vacancy_rate=min(1.0, resolved["vacancy_rate"] * shock["vacancy_multiplier"]),
            annual_operating_expenses=(resolved["annual_operating_expenses"] * shock["opex_multiplier"])
                if resolved["annual_operating_expenses"] is not None else None,
        )
        results[name] = run_financial_engine(shocked, observed)

    return results


def scenario_summary(scenario_results: dict) -> list:
    """Flattens the three scenarios into one comparison table (used by the
    report/CSV export)."""
    rows = []
    for name in ("Downside", "Base", "Upside"):
        r = scenario_results.get(name, {})
        m = r.get("metrics") or {}
        rows.append({
            "scenario": name,
            "validation_status": r.get("validation_status"),
            "irr": m.get("irr"),
            "npv": m.get("npv"),
            "roi_total_holding_period": m.get("roi_total_holding_period"),
            "cap_rate": m.get("cap_rate"),
            "cash_on_cash_return": m.get("cash_on_cash_return"),
        })
    return rows


# ---------------------------------------------------------- sensitivity
SENSITIVITY_DRIVERS = {
    "purchase_price": [-0.10, -0.05, 0.0, 0.05, 0.10],
    "monthly_rent": [-0.10, -0.05, 0.0, 0.05, 0.10],
    "vacancy_rate": [-0.5, 0.0, 0.5, 1.0, 2.0],           # multiplicative shift
    "annual_operating_expenses": [-0.10, -0.05, 0.0, 0.05, 0.10],
    "appreciation_rate": [-0.03, -0.015, 0.0, 0.015, 0.03],  # additive (percentage points)
    "holding_period_years": [-2, -1, 0, 1, 2],             # additive (years)
}


def run_sensitivity(base_assumptions: FinancialAssumptions, observed: dict) -> dict:
    """Section 6.6: varies one driver at a time around the Base case,
    holding all others fixed, and reports resulting IRR/NPV. Requires Base
    to be resolvable first (same reasoning as scenarios)."""
    base_result = run_financial_engine(base_assumptions, observed)
    if base_result["validation_status"] == "INSUFFICIENT DATA":
        return {"status": "INSUFFICIENT DATA",
                "reason": "Base case could not be resolved; sensitivity requires a valid baseline."}

    resolved = base_result["assumptions_used"]
    out = {}
    for driver, deltas in SENSITIVITY_DRIVERS.items():
        rows = []
        base_val = resolved.get(driver)
        if base_val is None:
            out[driver] = {"status": "INSUFFICIENT DATA", "reason": f"{driver} not resolvable in Base case"}
            continue
        for delta in deltas:
            kwargs = {}
            if driver in ("purchase_price", "monthly_rent", "annual_operating_expenses"):
                kwargs[driver] = base_val * (1 + delta)
            elif driver == "vacancy_rate":
                kwargs[driver] = min(1.0, max(0.0, base_val * (1 + delta)))
            elif driver == "appreciation_rate":
                kwargs[driver] = base_val + delta
            elif driver == "holding_period_years":
                kwargs[driver] = max(1, base_val + delta)

            shocked = replace(base_assumptions, **kwargs)
            r = run_financial_engine(shocked, observed)
            m = r.get("metrics") or {}
            rows.append({
                "driver_value": kwargs[driver],
                "delta_label": delta,
                "irr": m.get("irr"),
                "npv": m.get("npv"),
                "roi": m.get("roi_total_holding_period"),
            })
        out[driver] = {"status": "OK", "rows": rows}
    return out


if __name__ == "__main__":
    import json
    from data_loader import load_property_financials_from_csv

    observed = load_property_financials_from_csv(1)
    base = FinancialAssumptions(property_id=1, annual_operating_expenses=180000,
                                 vacancy_rate=0.05, appreciation_rate=0.08)
    scen = run_scenarios(base, observed)
    print(json.dumps(scenario_summary(scen), indent=2, default=str))


# In[ ]:



