"""
Phase 9, Section 9.4-9.8 -- Deterministic Decision Policy
==============================================================
The Decision Agent "must NOT independently invent the final decision. It
passes structured findings into the deterministic decision policy." This
module IS that deterministic policy -- pure arithmetic over the five agent
findings, no LLM involved anywhere in this file.

DECISION SCORE (§9.4) -- weighted sum of 5 component scores, each 0-100,
weights explicit/configurable/documented here (not hidden in a prompt):

  market_score      20%   MarketAgent's market_strength_score (reused from Phase 8)
  prediction_score   15%   from PredictionAgent's valuation_gap_pct (undervalued = higher)
  financial_score    25%   from FinanceAgent's IRR vs. discount rate
  risk_score         20%   from RiskAgent's simulated probability of negative NPV + stability
  geo_score          20%   GeoAgent's location_score (reused from Phase 8)

If a component is unavailable, its weight is redistributed proportionally
across the remaining available components -- never silently scored as 0
(same convention as Phase 8's location_score).

DECISION CONFIDENCE (§9.6) -- kept SEPARATE from decision_score. A high
score does not mean high confidence. Confidence is the mean of six
completeness/quality signals (data, model, evidence, financial, risk, geo),
each independently checked against what each agent actually reported --
notably, RiskAgent's contribution is capped at 60/100 regardless of how
"good" the simulated numbers look, because Phase 7's calibration_status is
always UNCALIBRATED (§7.7) and confidence must reflect that.

CRITICAL DECISION GATES (§9.7) -- checked BEFORE a score/confidence-based
label is allowed to stand. Any gate failure forces INSUFFICIENT, regardless
of how favorable the score looks.
"""
from dataclasses import dataclass


# ---------------------------------------------------------------- weights
COMPONENT_WEIGHTS = {
    "market_score": 0.20,
    "prediction_score": 0.15,
    "financial_score": 0.25,
    "risk_score": 0.20,
    "geo_score": 0.20,
}

# Decision-label thresholds on the 0-100 decision_score, and the minimum
# decision_confidence required to act on a score at face value. Documented
# business-judgement defaults (no historical outcome dataset exists in this
# platform to fit these against -- same honesty standard as every other
# threshold introduced across Phases 4/6/7/8).
INVEST_SCORE_THRESHOLD = 65.0
AVOID_SCORE_THRESHOLD = 35.0
MIN_CONFIDENCE_TO_ACT = 55.0
MIN_CONFIDENCE_FOR_ANY_LABEL = 30.0  # below this, INSUFFICIENT regardless of score


def _prediction_score(prediction_finding) -> float:
    """Undervalued-relative-to-model-estimate scores higher. gap_pct = 0 -> 50.
    Each 10 percentage points of (predicted - asking)/asking maps to +/-25
    points, capped at [0,100] -- documented linear mapping, not fitted."""
    if prediction_finding.status == "INSUFFICIENT DATA":
        return None
    gap = prediction_finding.metrics.get("valuation_gap_pct")
    if gap is None:
        return None
    return max(0.0, min(100.0, 50.0 + gap * 2.5))


def _financial_score(financial_finding) -> float:
    """IRR relative to the discount_rate used as the target return. Each 1
    percentage point of (IRR - target) maps to +/-5 points around 50,
    capped at [0,100] -- documented linear mapping, not fitted."""
    if financial_finding.status == "INSUFFICIENT DATA":
        return None
    irr = financial_finding.metrics.get("irr")
    if irr is None:
        return None
    # discount_rate isn't in FinanceAgent's flattened metrics; use Phase 6's
    # documented default (10%) unless the raw result says otherwise.
    target = financial_finding.raw["base_result"]["assumptions_used"].get("discount_rate", 0.10)
    return max(0.0, min(100.0, 50.0 + (irr - target) * 500))


def _risk_score(risk_finding) -> float:
    """Inverts probability of negative NPV (60% weight) and blends with
    decision stability (40% weight) -- both already 0-1/0-100 from Phase 7,
    just recombined here, not recomputed."""
    if risk_finding.status == "INSUFFICIENT DATA":
        return None
    p_neg = risk_finding.metrics.get("probability_negative_npv")
    stability = risk_finding.metrics.get("stability_pct")
    if p_neg is None or stability is None:
        return None
    return round(0.6 * (100 * (1 - p_neg)) + 0.4 * stability, 1)


def compute_component_scores(market_f, prediction_f, financial_f, risk_f, geo_f) -> dict:
    scores = {}
    if market_f.status != "INSUFFICIENT DATA":
        s = market_f.metrics.get("market_strength_score")
        if s is not None:
            scores["market_score"] = s
    ps = _prediction_score(prediction_f)
    if ps is not None:
        scores["prediction_score"] = ps
    fs = _financial_score(financial_f)
    if fs is not None:
        scores["financial_score"] = fs
    rs = _risk_score(risk_f)
    if rs is not None:
        scores["risk_score"] = rs
    if geo_f.status != "INSUFFICIENT DATA":
        s = geo_f.metrics.get("location_score")
        if s is not None:
            scores["geo_score"] = s
    return scores


def compute_decision_score(component_scores: dict) -> dict:
    if not component_scores:
        return {"decision_score": None, "weights_applied": {}, "components_missing": list(COMPONENT_WEIGHTS)}
    total_weight = sum(COMPONENT_WEIGHTS[k] for k in component_scores)
    renormalized = {k: COMPONENT_WEIGHTS[k] / total_weight for k in component_scores}
    decision_score = round(sum(component_scores[k] * renormalized[k] for k in component_scores), 1)
    missing = sorted(set(COMPONENT_WEIGHTS) - set(component_scores))
    return {"decision_score": decision_score, "weights_applied": {k: round(v, 3) for k, v in renormalized.items()},
            "components_missing": missing}


def compute_decision_confidence(data_f, market_f, prediction_f, financial_f, risk_f, geo_f,
                                 evidence_validation_f) -> dict:
    """§9.6. Six independent completeness/quality checks, averaged. Each is
    grounded in that agent's own reported status -- not re-derived from the
    score, which would conflate score and confidence (the exact mistake
    §9.6 warns against)."""
    STATUS_TO_CONF = {"PASS": 100.0, "PASS WITH LIMITATIONS": 65.0, "CONDITIONAL": 50.0,
                       "UNCALIBRATED": 60.0, "REJECTED": 0.0, "BLOCKED": 0.0, "INSUFFICIENT DATA": 0.0}

    components = {
        "data_quality": STATUS_TO_CONF.get(data_f.status, 0.0),
        "model_status": STATUS_TO_CONF.get(prediction_f.status, 0.0),
        "evidence_status": STATUS_TO_CONF.get(evidence_validation_f.status, 0.0),
        "financial_completeness": STATUS_TO_CONF.get(financial_f.status, 0.0),
        # Risk is hard-capped at 60 regardless of status text, since Phase 7's
        # calibration_status is ALWAYS "UNCALIBRATED" (§7.7) -- this is not
        # optional and must not be relaxed even if risk_f.status looks like "PASS".
        "risk_completeness": min(60.0, STATUS_TO_CONF.get(risk_f.status, 0.0)),
        "geo_completeness": STATUS_TO_CONF.get(geo_f.status, 0.0),
    }
    decision_confidence = round(sum(components.values()) / len(components), 1)
    return {"decision_confidence": decision_confidence, "components": components}


def check_critical_gates(data_f, financial_f, evidence_validation_f, decision_confidence: float) -> dict:
    """§9.7. Any failed gate forces INSUFFICIENT downstream, regardless of score."""
    gates = {
        "property_found": data_f.status != "INSUFFICIENT DATA",
        "financial_analysis_available": financial_f.status != "INSUFFICIENT DATA",
        "evidence_not_blocked": evidence_validation_f.status != "BLOCKED",
        "minimum_confidence_met": decision_confidence >= MIN_CONFIDENCE_FOR_ANY_LABEL,
    }
    gates["all_passed"] = all(gates.values())
    return gates


def decide(decision_score: float, decision_confidence: float, gates: dict) -> str:
    """§9.5 states. Deterministic, documented thresholds -- see module
    docstring for INVEST_SCORE_THRESHOLD / AVOID_SCORE_THRESHOLD /
    MIN_CONFIDENCE_TO_ACT."""
    if not gates["all_passed"] or decision_score is None:
        return "INSUFFICIENT"
    if decision_score >= INVEST_SCORE_THRESHOLD and decision_confidence >= MIN_CONFIDENCE_TO_ACT:
        return "INVEST"
    if decision_score <= AVOID_SCORE_THRESHOLD:
        return "AVOID"
    return "HOLD"  # covers: mid-range score, OR a high score without enough confidence to act on it


if __name__ == "__main__":
    print("COMPONENT_WEIGHTS:", COMPONENT_WEIGHTS)
    print("sum of weights:", sum(COMPONENT_WEIGHTS.values()))
