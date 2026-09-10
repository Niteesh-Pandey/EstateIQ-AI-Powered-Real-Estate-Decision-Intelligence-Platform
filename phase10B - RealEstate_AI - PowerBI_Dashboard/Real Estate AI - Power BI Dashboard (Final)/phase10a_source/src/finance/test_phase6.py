"""
Phase 6, Section 6.9 -- Testing
Run: python3 -m pytest src/finance/test_phase6.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

from data_loader import load_property_financials_from_csv, _locality_appreciation
from engine import (FinancialAssumptions, FinancingTerms, run_financial_engine,
                     irr, npv, payback_period, annual_debt_service)
from scenarios import run_scenarios, run_sensitivity, scenario_summary

import pandas as pd

OBSERVED_1 = load_property_financials_from_csv(1)


# --------------------------------------------------------------- data_loader
def test_property_not_found_returns_insufficient_data():
    result = load_property_financials_from_csv(999999999)
    assert result["status"] == "INSUFFICIENT DATA"


def test_observed_facts_are_tagged_observed():
    assert OBSERVED_1["governance"]["asking_price"] == "OBSERVED"
    assert OBSERVED_1["property_facts"]["asking_price"] > 0


def test_locality_appreciation_flags_unrealistic_cagr_as_unreliable():
    # Locality 54 was independently confirmed (audit) to have a CAGR > 100%/yr,
    # inherited from the Phase 3-documented generator compounding bug.
    mm = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "data", "processed", "market_monthly.csv"))
    result = _locality_appreciation(mm, 54)
    assert result["status"] == "OBSERVED_BUT_UNRELIABLE"
    assert result["reliable_for_use_as_default"] is False


def test_locality_appreciation_accepts_realistic_cagr():
    mm = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "data", "processed", "market_monthly.csv"))
    # locality 1 median-ish growth from earlier audit run was well under 20%/yr
    result = _locality_appreciation(mm, 1)
    if result["annualized_growth_rate"] is not None and abs(result["annualized_growth_rate"]) <= 0.20:
        assert result["reliable_for_use_as_default"] is True


def test_unreliable_appreciation_never_auto_used_as_default():
    """End-to-end: if the only appreciation signal available is flagged
    unreliable, the engine must NOT silently use it -- exit value must be
    None / status must reflect insufficient data, unless caller overrides."""
    from engine import resolve_inputs
    fake_observed = {
        "property_facts": {"asking_price": 1000000, "monthly_rent_listed": 5000},
        "observed_vacancy_rate": 0.05,
        "observed_annual_operating_expenses": {"total": 50000},
        "observed_locality_appreciation": {
            "status": "OBSERVED_BUT_UNRELIABLE", "annualized_growth_rate": 1.30,
            "reliable_for_use_as_default": False,
        },
    }
    a = FinancialAssumptions(property_id=1)
    resolved = resolve_inputs(a, fake_observed)
    assert resolved["appreciation_rate"] is None
    assert resolved["governance"]["appreciation_rate"] == "INSUFFICIENT DATA"


# ------------------------------------------------------------------- engine
def test_missing_required_inputs_returns_insufficient_data_not_a_guess():
    a = FinancialAssumptions(property_id=1)  # no opex/appreciation supplied
    result = run_financial_engine(a, OBSERVED_1)
    assert result["validation_status"] == "INSUFFICIENT DATA"
    assert result["metrics"] is None


def test_full_assumptions_produce_pass_status_and_positive_noi():
    a = FinancialAssumptions(property_id=1, annual_operating_expenses=180000,
                              vacancy_rate=0.05, appreciation_rate=0.08)
    result = run_financial_engine(a, OBSERVED_1)
    assert result["validation_status"] == "PASS"
    assert result["cash_flows"]["noi"] > 0


def test_noi_equals_egi_minus_opex():
    a = FinancialAssumptions(property_id=1, annual_operating_expenses=180000,
                              vacancy_rate=0.05, appreciation_rate=0.08)
    result = run_financial_engine(a, OBSERVED_1)
    cf = result["cash_flows"]
    assert round(cf["noi"], 2) == round(cf["effective_gross_income"] - cf["annual_operating_expenses"], 2)


def test_dscr_is_none_when_all_cash():
    a = FinancialAssumptions(property_id=1, annual_operating_expenses=180000,
                              vacancy_rate=0.05, appreciation_rate=0.08)
    result = run_financial_engine(a, OBSERVED_1)
    assert result["metrics"]["dscr"] is None


def test_dscr_is_numeric_when_leveraged():
    a = FinancialAssumptions(property_id=1, annual_operating_expenses=180000,
                              vacancy_rate=0.05, appreciation_rate=0.08,
                              financing=FinancingTerms(down_payment_pct=0.2,
                                                        loan_interest_rate=0.09, loan_term_years=20))
    result = run_financial_engine(a, OBSERVED_1)
    assert result["metrics"]["dscr"] is not None
    assert result["cash_flows"]["loan_amount"] > 0


def test_leveraged_deal_without_loan_terms_is_insufficient_data():
    a = FinancialAssumptions(property_id=1, annual_operating_expenses=180000,
                              vacancy_rate=0.05, appreciation_rate=0.08,
                              financing=FinancingTerms(down_payment_pct=0.2))  # rate/term missing
    result = run_financial_engine(a, OBSERVED_1)
    assert result["validation_status"] == "INSUFFICIENT DATA"


def test_no_exit_value_without_appreciation_or_cap_rate():
    a = FinancialAssumptions(property_id=1, annual_operating_expenses=180000, vacancy_rate=0.05)
    result = run_financial_engine(a, OBSERVED_1)
    # opex+vacancy present but no appreciation/cap-rate -> engine still runs
    # (NOI-level metrics computable) but exit value must be None, not guessed
    assert result["cash_flows"]["exit_value"] is None
    assert result["metrics"]["terminal_value_cagr"] is None


def test_irr_none_when_no_sign_change():
    # all-positive cash flows -> IRR mathematically undefined
    assert irr([100, 50, 50, 50]) is None


def test_irr_matches_known_case():
    # -1000 now, +1100 in one year => IRR = 10%
    result = irr([-1000, 1100])
    assert abs(result - 0.10) < 0.001


def test_npv_zero_at_irr():
    cash_flows = [-1000, 300, 300, 300, 300, 300]
    r = irr(cash_flows)
    assert abs(npv(cash_flows, r)) < 1.0


def test_payback_period_known_case():
    # -1000, then +250/yr => payback at year 4
    assert payback_period([-1000, 250, 250, 250, 250, 250]) == 4.0


def test_payback_period_none_when_never_recovered():
    assert payback_period([-1000, 50, 50, 50]) is None


def test_annual_debt_service_positive_for_valid_loan():
    ds = annual_debt_service(1000000, 0.09, 20)
    assert ds > 0
    # sanity: total payments over term should exceed principal (interest paid)
    assert ds * 20 > 1000000


# ---------------------------------------------------------------- scenarios
def test_scenario_ordering_downside_le_base_le_upside():
    a = FinancialAssumptions(property_id=1, annual_operating_expenses=180000,
                              vacancy_rate=0.05, appreciation_rate=0.08)
    results = run_scenarios(a, OBSERVED_1)
    rows = {r["scenario"]: r for r in scenario_summary(results)}
    assert rows["Downside"]["irr"] <= rows["Base"]["irr"] <= rows["Upside"]["irr"]
    assert rows["Downside"]["npv"] <= rows["Base"]["npv"] <= rows["Upside"]["npv"]


def test_scenarios_skip_stress_when_base_is_insufficient_data():
    a = FinancialAssumptions(property_id=1)  # no opex/appreciation
    results = run_scenarios(a, OBSERVED_1)
    assert results["Base"]["validation_status"] == "INSUFFICIENT DATA"
    assert results["Upside"]["validation_status"] == "INSUFFICIENT DATA"
    assert results["Downside"]["validation_status"] == "INSUFFICIENT DATA"


# -------------------------------------------------------------- sensitivity
def test_sensitivity_purchase_price_direction():
    a = FinancialAssumptions(property_id=1, annual_operating_expenses=180000,
                              vacancy_rate=0.05, appreciation_rate=0.08)
    sens = run_sensitivity(a, OBSERVED_1)
    rows = sens["purchase_price"]["rows"]
    irrs = [r["irr"] for r in rows]
    assert irrs == sorted(irrs, reverse=True)  # higher price -> lower IRR, monotonic


def test_sensitivity_requires_valid_base():
    a = FinancialAssumptions(property_id=1)
    sens = run_sensitivity(a, OBSERVED_1)
    assert sens["status"] == "INSUFFICIENT DATA"


def test_sensitivity_all_documented_drivers_present():
    a = FinancialAssumptions(property_id=1, annual_operating_expenses=180000,
                              vacancy_rate=0.05, appreciation_rate=0.08)
    sens = run_sensitivity(a, OBSERVED_1)
    for driver in ("purchase_price", "monthly_rent", "vacancy_rate",
                   "annual_operating_expenses", "appreciation_rate", "holding_period_years"):
        assert driver in sens


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
