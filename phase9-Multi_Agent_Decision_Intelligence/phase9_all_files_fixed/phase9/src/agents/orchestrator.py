"""
Phase 9, Section 9.9 -- End-to-End Flow
============================================
USER QUESTION -> QUERY UNDERSTANDING -> DATA AGENT -> MARKET AGENT ->
PREDICTION AGENT -> EVIDENCE AGENT -> FINANCE AGENT -> RISK AGENT ->
GEO AGENT -> EVIDENCE VALIDATOR -> DECISION POLICY -> DECISION RESULT ->
EXPLANATION

This module is the only place that calls every agent in sequence and
assembles the final `DecisionResult` (§9.8). No agent calls another agent
directly -- the orchestrator owns the flow, which is what makes each agent
independently testable (see test_phase9.py) and keeps the multi-agent
system "an orchestration layer, not the source of truth" (§9.1).
"""
import os
import sys
import time


_HERE = os.getcwd()
#_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from contracts import DecisionResult
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
from explanation_agent import explain_decision


def run_decision_pipeline(query, source: str = "csv", n_simulations: int = 2000,
                           financial_overrides: dict = None) -> dict:
    """Returns {"decision_result": dict, "explanation": str, "agent_trace": {...}}."""
    financial_overrides = financial_overrides or {}
    trace = {}

    intent_f = understand_query(query)
    trace["query_understanding"] = intent_f.to_dict()
    if intent_f.status == "INSUFFICIENT DATA":
        return _insufficient_result(None, "Query could not be understood.", trace)

    property_id = intent_f.raw["property_id"]

    data_f = get_property_facts(property_id, source=source)
    trace["data_agent"] = data_f.to_dict()
    if data_f.status == "INSUFFICIENT DATA":
        return _insufficient_result(property_id, f"property_id={property_id} not found.", trace)

    locality_id = data_f.raw.get("locality_id")
    locality_name = data_f.raw.get("locality_name")
    city_name = data_f.raw.get("city_name")

    market_f = get_market_snapshot(locality_id, source=source)
    trace["market_agent"] = market_f.to_dict()

    prediction_f = get_predictions(property_id)
    trace["prediction_agent"] = prediction_f.to_dict()

    evidence_f = get_evidence(locality_name, city_name)
    trace["evidence_agent"] = evidence_f.to_dict()

    predicted_valuation = prediction_f.metrics.get("predicted_valuation") if prediction_f.raw else None
    financial_f = get_financials(property_id, source=source, predicted_valuation=predicted_valuation,
                                  **financial_overrides)
    trace["finance_agent"] = financial_f.to_dict()

    risk_f = get_risk_analysis(property_id, source=source, n_simulations=n_simulations, **financial_overrides)
    trace["risk_agent"] = risk_f.to_dict()

    geo_f = get_geo_analysis(locality_id, source=source)
    trace["geo_agent"] = geo_f.to_dict()

    evidence_validation_f = validate_evidence(evidence_f)
    trace["evidence_validator"] = evidence_validation_f.to_dict()

    # ---------------------------------------------------------- Decision Policy
    component_scores = dp.compute_component_scores(market_f, prediction_f, financial_f, risk_f, geo_f)
    score_result = dp.compute_decision_score(component_scores)
    confidence_result = dp.compute_decision_confidence(data_f, market_f, prediction_f, financial_f,
                                                         risk_f, geo_f, evidence_validation_f)
    gates = dp.check_critical_gates(data_f, financial_f, evidence_validation_f,
                                     confidence_result["decision_confidence"])
    decision = dp.decide(score_result["decision_score"], confidence_result["decision_confidence"], gates)

    key_reasons, key_risks, assumptions, conditions, actions, limitations = _build_narrative(
        decision, data_f, market_f, prediction_f, financial_f, risk_f, geo_f, evidence_validation_f,
        score_result, confidence_result, gates)

    result = DecisionResult(
        property_id=property_id,
        decision=decision,
        decision_score=score_result["decision_score"],
        decision_confidence=confidence_result["decision_confidence"],
        market_findings=market_f.to_dict(),
        prediction_findings=prediction_f.to_dict(),
        financial_findings=financial_f.to_dict(),
        risk_findings=risk_f.to_dict(),
        geo_findings=geo_f.to_dict(),
        evidence={"summary": evidence_f.summary, "evidence_ids": evidence_f.evidence_ids,
                  "validation": evidence_validation_f.to_dict()},
        key_reasons=key_reasons, key_risks=key_risks, critical_assumptions=assumptions,
        conditions=conditions, recommended_actions=actions, limitations=limitations,
        data_quality_status=data_f.status, model_status=prediction_f.status,
        evidence_status=evidence_validation_f.status,
        component_scores=component_scores, gate_results=gates,
    ).to_dict()

    explanation = explain_decision(result)
    return {"decision_result": result, "explanation": explanation, "agent_trace": trace}


def _build_narrative(decision, data_f, market_f, prediction_f, financial_f, risk_f, geo_f,
                      evidence_validation_f, score_result, confidence_result, gates):
    reasons, risks, assumptions, conditions, actions, limitations = [], [], [], [], [], []

    if financial_f.status != "INSUFFICIENT DATA":
        m = financial_f.metrics
        reasons.append(f"Base-case IRR {m['irr']*100:.1f}%, NPV ₹{m['npv']:,.0f} (5-year hold).")
    if market_f.status != "INSUFFICIENT DATA":
        reasons.append(market_f.summary)
    if geo_f.status != "INSUFFICIENT DATA":
        reasons.append(f"Location score {geo_f.metrics['location_score']:.1f}/100.")
    if prediction_f.status != "INSUFFICIENT DATA" and prediction_f.metrics.get("valuation_gap_pct") is not None:
        reasons.append(f"Model-predicted valuation is {prediction_f.metrics['valuation_gap_pct']:+.1f}% "
                        "vs. asking price.")

    if risk_f.status != "INSUFFICIENT DATA":
        risks.append(f"{risk_f.metrics['probability_negative_npv']*100:.0f}% simulated probability of "
                      f"negative NPV (UNCALIBRATED -- see limitations).")
        risks.append(f"Top simulated risk driver: {risk_f.metrics.get('top_risk_driver')}.")
    if geo_f.raw and geo_f.raw.get("geo_risk", {}).get("flood_risk", {}).get("status") == "INSUFFICIENT DATA":
        risks.append("Flood/environmental risk data is not available for this locality (not a zero-risk "
                      "finding -- simply unmeasured).")

    if financial_f.raw and "base_result" in financial_f.raw:
        for k, v in financial_f.raw["base_result"]["assumptions_used"].get("governance", {}).items():
            if v == "ASSUMED_DEFAULT":
                assumptions.append(f"{k} was defaulted (no property-level or supplied data).")
    assumptions.extend(financial_f.limitations)

    if not gates["all_passed"]:
        failed = [k for k, v in gates.items() if k != "all_passed" and not v]
        conditions.append(f"Critical gate(s) not met: {failed}.")
    if decision == "HOLD" and score_result["decision_score"] is not None and \
            score_result["decision_score"] >= dp.INVEST_SCORE_THRESHOLD:
        conditions.append(f"Score ({score_result['decision_score']}) met the INVEST threshold but "
                           f"confidence ({confidence_result['decision_confidence']}) did not meet the "
                           f"{dp.MIN_CONFIDENCE_TO_ACT} minimum required to act on it.")

    if decision == "INSUFFICIENT":
        actions.append("Resolve the failed critical gate(s) above, or supply the missing inputs directly, "
                        "before this property can receive an INVEST/HOLD/AVOID decision.")
    elif decision == "HOLD":
        actions.append("Improve financial terms (price, financing) or wait for additional evidence/model "
                        "coverage before committing.")
    elif decision == "INVEST":
        actions.append("Proceed to legal/technical due diligence; confirm assumptions listed above with "
                        "the seller/agent before finalizing.")
    else:
        actions.append("Do not proceed at current terms; revisit if price or market conditions change.")

    if score_result["components_missing"]:
        limitations.append(f"Decision score components unavailable: {score_result['components_missing']}.")
    limitations.extend(risk_f.limitations)
    limitations.extend(geo_f.limitations)
    if evidence_validation_f.status != "PASS":
        limitations.append(f"Evidence validation status: {evidence_validation_f.status}.")

    return reasons, risks, assumptions, conditions, actions, limitations


def _insufficient_result(property_id, reason, trace) -> dict:
    result = DecisionResult(
        property_id=property_id if property_id is not None else -1,
        decision="INSUFFICIENT", decision_score=None, decision_confidence=0.0,
        market_findings={}, prediction_findings={}, financial_findings={}, risk_findings={}, geo_findings={},
        evidence={}, key_reasons=[], key_risks=[], critical_assumptions=[], conditions=[reason],
        recommended_actions=["Provide a valid property_id."], limitations=[reason],
        data_quality_status="INSUFFICIENT DATA", model_status="INSUFFICIENT DATA",
        evidence_status="INSUFFICIENT DATA",
    ).to_dict()
    return {"decision_result": result, "explanation": explain_decision(result), "agent_trace": trace}


if __name__ == "__main__":
    import json
    out = run_decision_pipeline("Should I invest in property 1?",
                                 financial_overrides={"annual_operating_expenses": 180000,
                                                       "vacancy_rate": 0.05, "appreciation_rate": 0.08})
    print(out["explanation"])
    print("\n--- decision_score / confidence ---")
    print(out["decision_result"]["decision_score"], out["decision_result"]["decision_confidence"])
