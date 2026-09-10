"""
Phase 7, Section 7.4 -- Monte Carlo Simulation Engine
=========================================================
Master Prompt Section 7.2 is explicit: "P7 must reuse the validated Phase 6
financial engine. Do NOT duplicate financial calculations." This module
never recomputes NOI/IRR/NPV itself -- every simulated draw is run through
`engine.run_financial_engine()` (byte-identical copy of the Phase 6 file),
exactly like a caller in Phase 9 would. Monte Carlo's only job is to
generate many plausible `FinancialAssumptions`, not to do finance math.

Distribution choice and why: Triangular(min, mode, max), not Normal. A
Normal distribution implies a std-dev estimated from real historical
volatility, which does not exist in this dataset at the deal level (no
repeated sales of the same unit, no time series of vacancy for a given
property). A Triangular distribution only requires a plausible min/mode/max
judgement call, which is what these really are -- and it visibly signals
"bounded judgement call", not "statistically fitted", which matters given
Section 7.7's calibration requirement below.

STATUS = UNCALIBRATED (Section 7.7): the min/mode/max bounds and the one
correlation used here are documented assumptions, not fitted against real
historical investment outcomes (no realized-IRR dataset exists to fit
against). Every MonteCarloResult carries this status explicitly, and it
must never be dropped or reworded downstream as if it were a validated
real-world probability.
"""
import copy
import os
import sys
from dataclasses import dataclass, replace
from typing import Optional

import numpy as np
from scipy.stats import norm, triang

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "finance"))
from engine import FinancialAssumptions, FinancingTerms, run_financial_engine  # noqa: E402


# ------------------------------------------------------- distribution spec
@dataclass
class TriangularSpec:
    """min/mode/max expressed as a multiplicative or additive shock around
    the Base-case resolved value. `kind='mult'` -> value * (1+shock);
    `kind='add'` -> value + shock (used for rate-type variables already
    expressed as a fraction, e.g. appreciation_rate, interest_rate)."""
    min_shock: float
    max_shock: float
    kind: str = "mult"  # 'mult' or 'add'

    def apply(self, base_value: float, u: float) -> float:
        """u is a uniform(0,1) draw already passed through the triangular
        inverse-CDF (see `sample_shocks`); this just maps shock -> value."""
        if self.kind == "mult":
            return base_value * (1 + u)
        return base_value + u


# Documented default distribution assumptions. All are ASSUMED judgement
# calls (Section 7.3's uncertain-variable list), overridable by a caller.
# Reasoning for each range is stated inline rather than left implicit.
DEFAULT_SPECS = {
    # Negotiation/closing-price uncertainty on top of the asking/assumed price -- narrow,
    # because purchase price is mostly a decision input, not a market-uncertain one.
    "purchase_price": TriangularSpec(min_shock=-0.05, max_shock=0.03, kind="mult"),
    "vacancy_rate": TriangularSpec(min_shock=-0.5, max_shock=1.5, kind="mult"),
    "annual_operating_expenses": TriangularSpec(min_shock=-0.10, max_shock=0.20, kind="mult"),
    "appreciation_rate": TriangularSpec(min_shock=-0.06, max_shock=0.06, kind="add"),
    "loan_interest_rate": TriangularSpec(min_shock=-0.015, max_shock=0.02, kind="add"),
}

# Documented, non-calibrated correlation: vacancy and operating expenses are
# assumed to move together in a weak local market (more vacancy often comes
# with higher marketing/turnover/maintenance cost) -- a plausible business
# relationship, not a number fitted to this dataset (no repeated-period
# panel of both variables for the same property exists to fit it from).
VACANCY_OPEX_CORRELATION = 0.4


@dataclass
class MonteCarloConfig:
    n_simulations: int = 2000
    seed: int = 42
    specs: dict = None  # falls back to DEFAULT_SPECS
    vacancy_opex_correlation: float = VACANCY_OPEX_CORRELATION
    target_irr: Optional[float] = None  # falls back to the assumptions' discount_rate

    def __post_init__(self):
        if self.specs is None:
            self.specs = DEFAULT_SPECS


def _triangular_u(rng_uniform_or_normal_cdf: np.ndarray, spec_key: str, specs: dict) -> np.ndarray:
    """Maps a uniform(0,1) array through Triangular(min_shock, 0, max_shock)'s
    inverse CDF, so 0.5 -> shock=0 (the mode = Base case, no shock)."""
    spec = specs[spec_key]
    lo, hi = spec.min_shock, spec.max_shock
    c = (0 - lo) / (hi - lo)  # mode position within [lo, hi], scaled to [0,1]
    return triang.ppf(rng_uniform_or_normal_cdf, c, loc=lo, scale=(hi - lo))


def run_monte_carlo(base_assumptions: FinancialAssumptions, observed: dict,
                     config: MonteCarloConfig = None) -> dict:
    config = config or MonteCarloConfig()
    base_result = run_financial_engine(base_assumptions, observed)
    if base_result["validation_status"] == "INSUFFICIENT DATA":
        return {
            "status": "INSUFFICIENT DATA",
            "calibration_status": "UNCALIBRATED",
            "reason": "Base case could not be resolved; Monte Carlo requires a valid, fully-resolved "
                      "starting point (same reasoning as Phase 6 scenarios/sensitivity).",
        }

    resolved = base_result["assumptions_used"]
    fin = resolved["financing"]
    is_leveraged = fin["down_payment_pct"] < 1.0

    rng = np.random.default_rng(config.seed)
    n = config.n_simulations

    # --- correlated draws for vacancy & opex via a Gaussian copula: two
    # correlated standard-normal shocks -> normal CDF -> triangular inverse-CDF.
    mean = [0, 0]
    cov = [[1, config.vacancy_opex_correlation], [config.vacancy_opex_correlation, 1]]
    z_vacancy, z_opex = rng.multivariate_normal(mean, cov, size=n).T
    u_vacancy = norm.cdf(z_vacancy)
    u_opex = norm.cdf(z_opex)

    u_price = rng.uniform(0, 1, size=n)
    u_appreciation = rng.uniform(0, 1, size=n)
    u_interest = rng.uniform(0, 1, size=n)

    specs = config.specs
    price_shock = _triangular_u(u_price, "purchase_price", specs)
    vacancy_shock = _triangular_u(u_vacancy, "vacancy_rate", specs)
    opex_shock = _triangular_u(u_opex, "annual_operating_expenses", specs)
    appreciation_shock = _triangular_u(u_appreciation, "appreciation_rate", specs)
    interest_shock = _triangular_u(u_interest, "loan_interest_rate", specs) if is_leveraged else None

    records = []
    n_insufficient = 0
    for i in range(n):
        sampled_price = specs["purchase_price"].apply(resolved["purchase_price"], price_shock[i])
        sampled_vacancy = min(1.0, max(0.0, specs["vacancy_rate"].apply(resolved["vacancy_rate"], vacancy_shock[i])))
        sampled_opex = specs["annual_operating_expenses"].apply(resolved["annual_operating_expenses"], opex_shock[i])
        sampled_appreciation = None
        if resolved["appreciation_rate"] is not None:
            sampled_appreciation = specs["appreciation_rate"].apply(resolved["appreciation_rate"],
                                                                      appreciation_shock[i])

        new_financing = fin
        if is_leveraged:
            sampled_rate = max(0.001, specs["loan_interest_rate"].apply(fin["loan_interest_rate"], interest_shock[i]))
            new_financing = FinancingTerms(down_payment_pct=fin["down_payment_pct"],
                                            loan_interest_rate=sampled_rate,
                                            loan_term_years=fin["loan_term_years"])
        else:
            new_financing = FinancingTerms(down_payment_pct=1.0)

        sampled = replace(
            base_assumptions,
            purchase_price=sampled_price,
            monthly_rent=resolved["monthly_rent"],
            vacancy_rate=sampled_vacancy,
            annual_operating_expenses=sampled_opex,
            appreciation_rate=sampled_appreciation,
            financing=new_financing,
        )
        result = run_financial_engine(sampled, observed)
        if result["validation_status"] == "INSUFFICIENT DATA":
            n_insufficient += 1
            continue
        m = result["metrics"]
        records.append({
            "irr": m["irr"], "npv": m["npv"], "roi": m["roi_total_holding_period"],
            "sampled_purchase_price": sampled_price, "sampled_vacancy_rate": sampled_vacancy,
            "sampled_opex": sampled_opex, "sampled_appreciation": sampled_appreciation,
        })

    return {
        "status": "OK",
        "calibration_status": "UNCALIBRATED",
        "calibration_note": "Distribution bounds and the vacancy/opex correlation are documented "
                             "judgement-call assumptions, not fitted to real historical investment "
                             "outcomes. Do not present these as real-world probabilities.",
        "n_simulations_requested": n,
        "n_simulations_valid": len(records),
        "n_simulations_insufficient_data": n_insufficient,
        "target_irr": config.target_irr if config.target_irr is not None else resolved["discount_rate"],
        "records": records,
        "base_result": base_result,
    }


if __name__ == "__main__":
    import json
    sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "finance"))
    from data_loader import load_property_financials_from_csv

    observed = load_property_financials_from_csv(1)
    base = FinancialAssumptions(property_id=1, annual_operating_expenses=180000,
                                 vacancy_rate=0.05, appreciation_rate=0.08)
    result = run_monte_carlo(base, observed, MonteCarloConfig(n_simulations=500))
    print("status:", result["status"], "valid:", result["n_simulations_valid"],
          "insufficient:", result["n_simulations_insufficient_data"])
    irrs = [r["irr"] for r in result["records"] if r["irr"] is not None]
    print("IRR mean:", round(np.mean(irrs), 4), "IRR p5:", round(np.percentile(irrs, 5), 4))
