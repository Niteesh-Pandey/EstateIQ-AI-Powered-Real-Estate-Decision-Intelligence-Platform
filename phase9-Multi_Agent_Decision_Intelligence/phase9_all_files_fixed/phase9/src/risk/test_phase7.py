"""
Phase 7, Section 7.10 -- Testing
Run: python3 -m pytest src/risk/test_phase7.py -q
"""
import os
import sys


_HERE = os.path.abspath('')
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "finance"))

import numpy as np
import pytest

from data_loader import load_property_financials_from_csv
from engine import FinancialAssumptions, FinancingTerms
from monte_carlo import run_monte_carlo, MonteCarloConfig, DEFAULT_SPECS
from risk_metrics import compute_risk_metrics
from decision_stability import compute_decision_stability, classify_financial_outcome
from scenario_engine import run_extended_scenarios, extended_scenario_summary

OBSERVED_1 = load_property_financials_from_csv(1)
BASE_ASSUMPTIONS = FinancialAssumptions(property_id=1, annual_operating_expenses=180000,
                                         vacancy_rate=0.05, appreciation_rate=0.08)


# ----------------------------------------------------------- Monte Carlo
def test_reproducibility_same_seed_same_result():
    r1 = run_monte_carlo(BASE_ASSUMPTIONS, OBSERVED_1, MonteCarloConfig(n_simulations=300, seed=7))
    r2 = run_monte_carlo(BASE_ASSUMPTIONS, OBSERVED_1, MonteCarloConfig(n_simulations=300, seed=7))
    irrs1 = [r["irr"] for r in r1["records"]]
    irrs2 = [r["irr"] for r in r2["records"]]
    assert irrs1 == irrs2


def test_different_seed_gives_different_samples():
    r1 = run_monte_carlo(BASE_ASSUMPTIONS, OBSERVED_1, MonteCarloConfig(n_simulations=300, seed=1))
    r2 = run_monte_carlo(BASE_ASSUMPTIONS, OBSERVED_1, MonteCarloConfig(n_simulations=300, seed=2))
    irrs1 = [r["irr"] for r in r1["records"]]
    irrs2 = [r["irr"] for r in r2["records"]]
    assert irrs1 != irrs2


def test_sample_size_matches_request_when_no_insufficient_draws():
    r = run_monte_carlo(BASE_ASSUMPTIONS, OBSERVED_1, MonteCarloConfig(n_simulations=500, seed=1))
    assert r["n_simulations_valid"] + r["n_simulations_insufficient_data"] == 500


def test_monte_carlo_requires_resolvable_base_case():
    unresolvable = FinancialAssumptions(property_id=1)  # no opex/appreciation supplied
    r = run_monte_carlo(unresolvable, OBSERVED_1, MonteCarloConfig(n_simulations=200))
    assert r["status"] == "INSUFFICIENT DATA"


def test_calibration_status_is_always_uncalibrated():
    r = run_monte_carlo(BASE_ASSUMPTIONS, OBSERVED_1, MonteCarloConfig(n_simulations=200))
    assert r["calibration_status"] == "UNCALIBRATED"


def test_simulated_mean_irr_close_to_base_case_irr():
    """Triangular shocks are centered on 0 (mode=Base value), so the
    simulated distribution should be centered near the Base-case point
    estimate -- not systematically biased up or down."""
    from engine import run_financial_engine
    base_irr = run_financial_engine(BASE_ASSUMPTIONS, OBSERVED_1)["metrics"]["irr"]
    r = run_monte_carlo(BASE_ASSUMPTIONS, OBSERVED_1, MonteCarloConfig(n_simulations=3000, seed=99))
    irrs = np.array([x["irr"] for x in r["records"] if x["irr"] is not None])
    assert abs(irrs.mean() - base_irr) < 0.02  # within 2 percentage points


def test_leverage_widens_irr_distribution():
    levered = FinancialAssumptions(property_id=1, annual_operating_expenses=180000, vacancy_rate=0.05,
                                    appreciation_rate=0.08,
                                    financing=FinancingTerms(down_payment_pct=0.2, loan_interest_rate=0.09,
                                                              loan_term_years=20))
    r_unlevered = run_monte_carlo(BASE_ASSUMPTIONS, OBSERVED_1, MonteCarloConfig(n_simulations=1000, seed=5))
    r_levered = run_monte_carlo(levered, OBSERVED_1, MonteCarloConfig(n_simulations=1000, seed=5))
    std_unlevered = np.std([x["irr"] for x in r_unlevered["records"] if x["irr"] is not None])
    std_levered = np.std([x["irr"] for x in r_levered["records"] if x["irr"] is not None])
    assert std_levered > std_unlevered


def test_vacancy_opex_correlation_is_positive_in_samples():
    """Sanity check that the documented vacancy/opex correlation (rho=0.4)
    actually shows up in the drawn samples, not just the config."""
    r = run_monte_carlo(BASE_ASSUMPTIONS, OBSERVED_1, MonteCarloConfig(n_simulations=3000, seed=11))
    vac = np.array([x["sampled_vacancy_rate"] for x in r["records"]])
    opex = np.array([x["sampled_opex"] for x in r["records"]])
    corr = np.corrcoef(vac, opex)[0, 1]
    assert corr > 0.2  # should be meaningfully positive, close to the configured 0.4


# ------------------------------------------------------------- risk_metrics
def test_var_is_worse_than_or_equal_to_cvar_at_same_confidence():
    """CVaR (average of the tail beyond VaR) must be <= VaR itself for a
    loss-side (left-tail) metric -- the tail average can't be better than
    its own threshold."""
    r = run_monte_carlo(BASE_ASSUMPTIONS, OBSERVED_1, MonteCarloConfig(n_simulations=2000, seed=3))
    risk = compute_risk_metrics(r)
    assert risk["cvar_95_npv"] <= risk["var_95_npv"]
    assert risk["cvar_90_npv"] <= risk["var_90_npv"]


def test_roi_distribution_is_net_return_not_gross_multiple():
    """Regression test tied to the Phase 6 audit fix (engine.py
    compute_metrics): roi_total_holding_period is a NET return
    ((total cash received - equity invested) / equity invested), not a
    gross cash multiple. src/finance/engine.py here is a byte-identical
    copy of Phase 6's file, so if a future re-copy ever silently reverts to
    the old formula, this test catches it from Phase 7's own pipeline too.
    For a single-period (holding_period_years=1), unlevered deal, ROI and
    IRR must be numerically identical (same definition, same cash-flow pair)."""
    single_period = FinancialAssumptions(property_id=1, annual_operating_expenses=180000,
                                          vacancy_rate=0.05, appreciation_rate=0.08,
                                          holding_period_years=1)
    from engine import run_financial_engine
    base = run_financial_engine(single_period, OBSERVED_1)
    assert abs(base["metrics"]["roi_total_holding_period"] - base["metrics"]["irr"]) < 0.001

    r = run_monte_carlo(single_period, OBSERVED_1, MonteCarloConfig(n_simulations=500, seed=13))
    risk = compute_risk_metrics(r)
    # Mean simulated ROI should be in the same broad neighborhood as mean
    # simulated IRR for a single-period deal -- NOT offset by ~1.0 (100
    # percentage points), which is exactly the signature the old bug left.
    assert abs(risk["roi_distribution"]["mean"] - risk["irr_distribution"]["mean"]) < 0.05


def test_probabilities_between_0_and_1():
    r = run_monte_carlo(BASE_ASSUMPTIONS, OBSERVED_1, MonteCarloConfig(n_simulations=1000, seed=3))
    risk = compute_risk_metrics(r)
    for key in ("probability_negative_npv", "probability_negative_irr", "probability_meets_target_irr"):
        assert 0.0 <= risk[key] <= 1.0


def test_risk_metrics_insufficient_data_when_mc_insufficient():
    unresolvable = FinancialAssumptions(property_id=1)
    r = run_monte_carlo(unresolvable, OBSERVED_1, MonteCarloConfig(n_simulations=100))
    risk = compute_risk_metrics(r)
    assert risk["status"] == "INSUFFICIENT DATA"


def test_risk_drivers_appreciation_dominates_this_deal():
    """For this specific deal (short holding period, exit-value-driven cash
    flow), appreciation should be the strongest IRR driver -- verifies the
    Pearson-correlation ranking is actually doing something sensible, not
    just returning arbitrary numbers."""
    r = run_monte_carlo(BASE_ASSUMPTIONS, OBSERVED_1, MonteCarloConfig(n_simulations=2000, seed=3))
    risk = compute_risk_metrics(r)
    top_driver = risk["risk_drivers_ranked"][0]["driver"]
    assert top_driver == "appreciation"


# --------------------------------------------------------- decision_stability
def test_classify_financial_outcome_invest():
    assert classify_financial_outcome(0.15, 500000, 0.10) == "INVEST"


def test_classify_financial_outcome_avoid():
    assert classify_financial_outcome(-0.05, -500000, 0.10) == "AVOID"


def test_classify_financial_outcome_hold_when_mixed():
    assert classify_financial_outcome(0.05, -100000, 0.10) == "HOLD"


def test_decision_distribution_sums_to_100():
    r = run_monte_carlo(BASE_ASSUMPTIONS, OBSERVED_1, MonteCarloConfig(n_simulations=1000, seed=3))
    stability = compute_decision_stability(r)
    total = sum(stability["decision_distribution_pct"].values())
    assert abs(total - 100.0) < 0.5  # rounding tolerance


def test_stability_flags_when_base_case_is_minority():
    """Construct an artificial mc_result where the Base case label
    disagrees with the simulated majority, and confirm `unstable=True`."""
    fake_mc = {
        "status": "OK", "target_irr": 0.10,
        "records": [{"irr": 0.15, "npv": 100} for _ in range(80)] +
                   [{"irr": 0.02, "npv": -100} for _ in range(20)],
        "base_result": {"metrics": {"irr": 0.02, "npv": -100}},  # Base = HOLD, majority = INVEST
    }
    stability = compute_decision_stability(fake_mc)
    assert stability["majority_label"] == "INVEST"
    assert stability["base_case_label"] == "HOLD"
    assert stability["unstable"] is True


# ----------------------------------------------------------- scenario_engine
def test_severe_downside_worse_than_downside():
    results = run_extended_scenarios(BASE_ASSUMPTIONS, OBSERVED_1)
    rows = {r["scenario"]: r for r in extended_scenario_summary(results)}
    assert rows["Severe Downside"]["irr"] <= rows["Downside"]["irr"]
    assert rows["Severe Downside"]["npv"] <= rows["Downside"]["npv"]


def test_full_ordering_across_four_scenarios():
    results = run_extended_scenarios(BASE_ASSUMPTIONS, OBSERVED_1)
    rows = {r["scenario"]: r for r in extended_scenario_summary(results)}
    ordered = [rows["Severe Downside"]["irr"], rows["Downside"]["irr"],
               rows["Base"]["irr"], rows["Upside"]["irr"]]
    assert ordered == sorted(ordered)


def test_severe_downside_skipped_when_base_insufficient():
    unresolvable = FinancialAssumptions(property_id=1)
    results = run_extended_scenarios(unresolvable, OBSERVED_1)
    assert results["Severe Downside"]["validation_status"] == "INSUFFICIENT DATA"

if __name__ == "__main__":
    pytest.main(["test_phase7.py", "-q"])
    
#if __name__ == "__main__":
   # sys.exit(pytest.main(["src/risk/test_phase7.py", "-q"]))