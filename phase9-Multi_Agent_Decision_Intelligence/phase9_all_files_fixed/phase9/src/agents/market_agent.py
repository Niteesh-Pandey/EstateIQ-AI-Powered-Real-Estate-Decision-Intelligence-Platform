"""
Phase 9, Section 9.2 -- Market Agent
========================================
Uses: Phase 2 SQL (semantically -- `market_monthly` is the same table
Phase 2's SQL views summarize), Phase 3 analytics (informed the choice of
demand/supply/absorption as the relevant indicators), Phase 5 evidence
(via the Evidence Agent, combined at orchestration time).

Reuses Phase 8's `data_loader._market_intelligence()` and
`location_score._market_strength_score()` UNCHANGED -- the exact same
locality market snapshot and 0-100 market-strength normalization Phase 8
already built and tested (including the P5/P95 anchor fix documented in
Phase 8's report). This agent does not recompute market math; it packages
Phase 8's existing computation as a Market finding.
"""
import os
import sys

import pandas as pd

_HERE = os.getcwd()
#_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "geo"))
from contracts import AgentFinding
from geo_data_loader import _market_intelligence  # reused from Phase 8, unchanged
from location_score import _market_strength_score  # reused from Phase 8, unchanged

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "data", "processed")


def get_market_snapshot(locality_id: int, source: str = "csv") -> AgentFinding:
    if locality_id is None:
        return AgentFinding(
            agent_name="MarketAgent", status="INSUFFICIENT DATA", finding_type="market_snapshot",
            summary="No locality_id available (Data Agent could not resolve one).",
            source="market_monthly", confidence=0.0,
            limitations=["Market Agent requires a resolved locality_id from the Data Agent."],
        )

    market_monthly = pd.read_csv(os.path.join(_DATA_DIR, "market_monthly.csv"))
    market_intel = _market_intelligence(market_monthly, locality_id)

    if market_intel.get("status") != "OBSERVED":
        return AgentFinding(
            agent_name="MarketAgent", status="INSUFFICIENT DATA", finding_type="market_snapshot",
            summary=f"No market_monthly history found for locality_id={locality_id}.",
            source="core.market_monthly", confidence=0.0,
            limitations=["No locality-level market history available."],
        )

    market_strength = _market_strength_score(market_intel)
    summary = (f"Locality {locality_id}: demand index {market_intel['latest_demand_index']:.1f}, "
               f"supply index {market_intel['latest_supply_index']:.1f}, "
               f"absorption rate {market_intel['latest_absorption_rate']:.2f} "
               f"(as of {market_intel['latest_month']}).")

    return AgentFinding(
        agent_name="MarketAgent", status="PASS", finding_type="market_snapshot",
        summary=summary,
        metrics={
            "market_strength_score": market_strength,
            "latest_demand_index": market_intel["latest_demand_index"],
            "latest_supply_index": market_intel["latest_supply_index"],
            "latest_absorption_rate": market_intel["latest_absorption_rate"],
            "n_months_observed": market_intel["n_months_observed"],
        },
        source="core.market_monthly (reuses Phase 8 market_intelligence + market_strength_score unchanged)",
        confidence=90.0 if market_intel["n_months_observed"] >= 12 else 60.0,
        limitations=[] if market_intel["n_months_observed"] >= 12 else
                     [f"Only {market_intel['n_months_observed']} months of market history observed "
                      "(< 12) -- market_strength_score is based on limited history."],
        raw=market_intel,
    )


if __name__ == "__main__":
    print(get_market_snapshot(2).to_dict())
