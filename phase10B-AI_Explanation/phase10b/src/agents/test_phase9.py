"""
Phase 9 -- Testing (Master Prompt Section 12: Agent Tests -- routing,
contracts, missing data, evidence gates, deterministic decision; and the
E2E Test -- process "Should I invest in Property X?" and produce a complete
DecisionResult).
Run: python3 -m pytest src/agents/test_phase9.py -q
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import pytest

from contracts import AgentFinding
from query_understanding import understand_query
from data_agent import get_property_facts
from market_agent import get_market_snapshot
from prediction_agent import get_predictions
from evidence_agent import get_evidence
from finance_agent import get_financials
from risk_agent import get_risk_analysis
from geo_agent import get_geo_analysis
from evidence_validator import validate_evidence
import decision_policy as dp
from orchestrator import run_decision_pipeline

INVEST_PROPERTY = 2731    # confirmed INVEST during build
AVOID_PROPERTY = 1256     # confirmed AVOID during build
INSUFFICIENT_PROPERTY = 1  # confirmed INSUFFICIENT (no expense/rental history) during build


# ------------------------------------------------------------ Query Understanding
def test_query_understanding_extracts_int():
    f = understand_query(17)
    assert f.status == "PASS" and f.raw["property_id"] == 17


def test_query_understanding_extracts_from_sentence():
    f = understand_query("Should I invest in property 4021?")
    assert f.status == "PASS" and f.raw["property_id"] == 4021


def test_query_understanding_insufficient_when_no_id():
    f = understand_query("what a nice day")
    assert f.status == "INSUFFICIENT DATA"


# ------------------------------------------------------------------- Data Agent
def test_data_agent_finds_real_property():
    f = get_property_facts(1)
    assert f.status == "PASS"
    assert f.raw["locality_id"] is not None


def test_data_agent_insufficient_for_unknown_property():
    f = get_property_facts(999999999)
    assert f.status == "INSUFFICIENT DATA"


# ----------------------------------------------------------------- Market Agent
def test_market_agent_reuses_phase8_market_strength():
    """Regression guard: Market Agent must produce the SAME market_strength_score
    Phase 8's location_score module would for the same locality (proves reuse,
    not reimplementation)."""
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "geo"))
    from geo_data_loader import _market_intelligence
    from location_score import _market_strength_score
    import pandas as pd
    mm = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(_HERE)), "data", "processed",
                                    "market_monthly.csv"))
    expected = _market_strength_score(_market_intelligence(mm, 2))

    f = get_market_snapshot(2)
    assert f.metrics["market_strength_score"] == expected


def test_market_agent_insufficient_without_locality_id():
    f = get_market_snapshot(None)
    assert f.status == "INSUFFICIENT DATA"


# -------------------------------------------------------------- Prediction Agent
def test_prediction_agent_never_calls_rejected_models():
    f = get_predictions(1)
    limitation_text = " ".join(f.limitations)
    assert "dom_v1_gbr is REJECTED" in limitation_text
    assert "sale_probability_v1_gbr is REJECTED" in limitation_text
    # and confirm the metrics dict has no DOM/sale-probability keys at all
    assert "days_on_market" not in f.metrics
    assert "sale_probability" not in f.metrics


def test_prediction_agent_produces_valuation_and_rent():
    f = get_predictions(1)
    assert "predicted_valuation" in f.metrics
    assert "predicted_rent" in f.metrics
    assert f.status == "PASS WITH LIMITATIONS"  # matches Phase 4 registry tier for both models


def test_prediction_agent_insufficient_for_unknown_property():
    f = get_predictions(999999999)
    assert f.status == "INSUFFICIENT DATA"


# ---------------------------------------------------------------- Evidence Agent
def test_evidence_agent_citations_resolve_to_real_ids():
    f = get_evidence("Kakar Extension", "Delhi NCR")
    assert f.status in ("PASS", "PASS WITH LIMITATIONS")
    lookup = f.raw["evidence_lookup"]
    assert all(eid in lookup for eid in f.evidence_ids)


def test_evidence_agent_insufficient_without_locality():
    f = get_evidence(None, None)
    assert f.status == "INSUFFICIENT DATA"


# ------------------------------------------------------------- Evidence Validator
def test_evidence_validator_passes_correctly_grounded_summary():
    ef = get_evidence("Kakar Extension", "Delhi NCR")
    vf = validate_evidence(ef)
    assert vf.status in ("PASS", "PASS WITH LIMITATIONS")  # not BLOCKED


def test_evidence_validator_no_cross_document_contamination():
    """Regression test for the citation-placement bug found during build:
    across a spread of localities, no evidence summary should ever be
    BLOCKED due to a citation marker capturing the WRONG document's numbers."""
    from data_agent import get_property_facts
    for pid in (1, 2731, 1256, 195, 5923):
        facts = get_property_facts(pid)
        if facts.status == "INSUFFICIENT DATA":
            continue
        ef = get_evidence(facts.raw["locality_name"], facts.raw["city_name"])
        vf = validate_evidence(ef)
        assert vf.status != "BLOCKED", f"property {pid}: evidence BLOCKED unexpectedly"


def test_evidence_validator_insufficient_when_no_evidence():
    ef = get_evidence(None, None)
    vf = validate_evidence(ef)
    assert vf.status == "INSUFFICIENT DATA"


# ---------------------------------------------------------------- Finance Agent
def test_finance_agent_insufficient_without_expense_data():
    """Property 1 has no expense/rental records (confirmed during Phase 6
    build) -- Finance Agent must return INSUFFICIENT DATA, not guess."""
    f = get_financials(1)
    assert f.status == "INSUFFICIENT DATA"


def test_finance_agent_pass_with_explicit_assumptions():
    f = get_financials(1, annual_operating_expenses=180000, vacancy_rate=0.05, appreciation_rate=0.08)
    assert f.status == "PASS"
    assert f.metrics["irr"] is not None


# ------------------------------------------------------------------- Risk Agent
def test_risk_agent_status_always_uncalibrated():
    f = get_risk_analysis(1, annual_operating_expenses=180000, vacancy_rate=0.05,
                           appreciation_rate=0.08, n_simulations=300)
    assert f.status == "UNCALIBRATED"


def test_risk_agent_confidence_capped_at_60():
    f = get_risk_analysis(1, annual_operating_expenses=180000, vacancy_rate=0.05,
                           appreciation_rate=0.08, n_simulations=300)
    assert f.confidence <= 60.0


# -------------------------------------------------------------------- Geo Agent
def test_geo_agent_flood_risk_always_insufficient():
    f = get_geo_analysis(2)
    assert f.metrics["flood_risk_status"] == "INSUFFICIENT DATA"


def test_geo_agent_insufficient_without_locality_id():
    f = get_geo_analysis(None)
    assert f.status == "INSUFFICIENT DATA"


# ---------------------------------------------------------------- Decision Policy
def test_decision_policy_weights_sum_to_one():
    assert abs(sum(dp.COMPONENT_WEIGHTS.values()) - 1.0) < 1e-9


def test_decision_score_renormalizes_when_component_missing():
    scores = {"market_score": 60, "geo_score": 70}
    result = dp.compute_decision_score(scores)
    assert abs(sum(result["weights_applied"].values()) - 1.0) < 1e-6
    assert set(result["components_missing"]) == {"prediction_score", "financial_score", "risk_score"}


def test_decision_score_none_when_no_components():
    result = dp.compute_decision_score({})
    assert result["decision_score"] is None


def test_gate_failure_forces_insufficient():
    gates = {"property_found": True, "financial_analysis_available": False,
             "evidence_not_blocked": True, "minimum_confidence_met": True, "all_passed": False}
    assert dp.decide(90.0, 90.0, gates) == "INSUFFICIENT"


def test_high_score_low_confidence_becomes_hold_not_invest():
    gates = {"property_found": True, "financial_analysis_available": True,
             "evidence_not_blocked": True, "minimum_confidence_met": True, "all_passed": True}
    decision = dp.decide(80.0, 40.0, gates)  # score above INVEST threshold, confidence below MIN_CONFIDENCE_TO_ACT
    assert decision == "HOLD"


def test_decide_invest_avoid_hold_thresholds():
    gates = {"property_found": True, "financial_analysis_available": True,
             "evidence_not_blocked": True, "minimum_confidence_met": True, "all_passed": True}
    assert dp.decide(70.0, 80.0, gates) == "INVEST"
    assert dp.decide(20.0, 80.0, gates) == "AVOID"
    assert dp.decide(50.0, 80.0, gates) == "HOLD"


def test_risk_completeness_capped_regardless_of_status_text():
    """Confidence's risk_completeness component must never exceed 60,
    reflecting Phase 7's permanent UNCALIBRATED status (Section 7.7/9.6),
    even though RiskAgent's own .status field literally reads 'UNCALIBRATED'
    (not a low-looking string like 'REJECTED')."""
    from contracts import AgentFinding
    fake_risk = AgentFinding(agent_name="RiskAgent", status="UNCALIBRATED", finding_type="risk_analysis",
                              summary="", confidence=60.0)
    fake_pass = AgentFinding(agent_name="X", status="PASS", finding_type="x", summary="", confidence=100.0)
    result = dp.compute_decision_confidence(fake_pass, fake_pass, fake_pass, fake_pass, fake_risk, fake_pass,
                                             fake_pass)
    assert result["components"]["risk_completeness"] <= 60.0


# ------------------------------------------------------------------- End-to-End
def test_e2e_invest_decision():
    out = run_decision_pipeline(INVEST_PROPERTY)
    assert out["decision_result"]["decision"] == "INVEST"
    assert out["decision_result"]["decision_score"] is not None
    assert out["decision_result"]["decision_confidence"] is not None
    assert len(out["explanation"]) > 0


def test_e2e_avoid_decision():
    out = run_decision_pipeline(AVOID_PROPERTY)
    assert out["decision_result"]["decision"] == "AVOID"


def test_e2e_insufficient_decision_missing_financial_data():
    out = run_decision_pipeline(INSUFFICIENT_PROPERTY)
    assert out["decision_result"]["decision"] == "INSUFFICIENT"


def test_e2e_insufficient_for_unknown_property():
    out = run_decision_pipeline(999999999)
    assert out["decision_result"]["decision"] == "INSUFFICIENT"


def test_e2e_insufficient_for_unparseable_query():
    out = run_decision_pipeline("no id here")
    assert out["decision_result"]["decision"] == "INSUFFICIENT"


def test_e2e_decision_result_has_all_contract_fields():
    out = run_decision_pipeline(INVEST_PROPERTY)
    d = out["decision_result"]
    for field in ("property_id", "decision", "decision_score", "decision_confidence",
                  "market_findings", "prediction_findings", "financial_findings", "risk_findings",
                  "geo_findings", "evidence", "key_reasons", "key_risks", "critical_assumptions",
                  "conditions", "recommended_actions", "limitations", "data_quality_status",
                  "model_status", "evidence_status"):
        assert field in d, f"missing DecisionResult field: {field}"


def test_e2e_explanation_never_alters_decision_score():
    """The Explanation Agent must not change the underlying decision_score
    -- confirm the number printed in the explanation text matches the
    structured DecisionResult exactly."""
    out = run_decision_pipeline(INVEST_PROPERTY)
    score_str = str(out["decision_result"]["decision_score"])
    assert score_str in out["explanation"]


def test_e2e_deterministic_reproducibility():
    """Same property, same inputs -> same decision every time (no
    hidden randomness anywhere in the pipeline outside Risk Agent's fixed
    seed, which is itself deterministic)."""
    out1 = run_decision_pipeline(INVEST_PROPERTY)
    out2 = run_decision_pipeline(INVEST_PROPERTY)
    assert out1["decision_result"]["decision"] == out2["decision_result"]["decision"]
    assert out1["decision_result"]["decision_score"] == out2["decision_result"]["decision_score"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
