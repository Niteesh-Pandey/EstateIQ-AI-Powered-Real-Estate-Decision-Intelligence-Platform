"""
Phase 10B -- Testing.
Run: python3 -m pytest src/explanation/test_phase10b.py -q

IMPORTANT: no GEMINI_API_KEY was available in this build sandbox (same
situation as "no live PostgreSQL" in every prior phase). Tests that need to
exercise the LLM-response-handling path use `unittest.mock.patch` on
`_call_gemini` to supply a synthetic response -- this tests the
validation/fallback logic thoroughly and honestly, without pretending a
live API call happened. Tests that check the NO-KEY path make a real call
with no key, which is the actual code path a caller hits without
credentials configured.
"""
import os
import sys
from unittest.mock import patch

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "agents"))

import pytest

from numeric_fidelity_validator import validate_fidelity, extract_protected_numbers, _numbers_in_text
from ai_explanation_layer import generate_ai_explanation
from orchestrator import run_decision_pipeline

FAKE_RESULT = {
    "decision": "INVEST", "decision_score": 69.2, "decision_confidence": 81.7,
    "financial_findings": {"metrics": {"irr": 0.129, "npv": 2847332, "cap_rate": 0.041,
                                         "roi_total_holding_period": 1.62, "dscr": None}},
    "risk_findings": {"metrics": {"probability_negative_npv": 0.18, "probability_meets_target_irr": 0.82}},
    "geo_findings": {"metrics": {"location_score": 58.3}},
    "market_findings": {"metrics": {"market_strength_score": 61.0}},
}

REAL_INVEST_RESULT = run_decision_pipeline(2731)["decision_result"]
REAL_AVOID_RESULT = run_decision_pipeline(1256)["decision_result"]


# --------------------------------------------------------- Numeric extraction
def test_numbers_in_text_does_not_swallow_sentence_period():
    """Regression test for the bug found during build: '2,847,332.' must
    extract as '2847332', not '2847332.' with a trailing dot that never
    matches any representation."""
    nums = _numbers_in_text("NPV is ₹2,847,332. IRR is 12.9%.")
    assert "2847332" in nums
    assert "12.9" in nums
    assert "2847332." not in nums


def test_extract_protected_numbers_skips_missing_fields():
    sparse = {"decision": "HOLD", "decision_score": 50.0, "decision_confidence": 60.0}
    protected = extract_protected_numbers(sparse)
    assert len(protected) == 2  # only decision_score and decision_confidence present


# -------------------------------------------------------- Fidelity validator
def test_faithful_explanation_passes():
    text = ("DECISION: INVEST. Decision score 69.2/100, confidence 81.7/100. "
            "IRR is 12.9%, NPV is ₹2,847,332. Cap rate 4.1%. ROI 162%. "
            "18% probability of negative NPV. 82% probability of meeting target IRR. "
            "Location score 58.3. Market strength score 61.0.")
    report = validate_fidelity(FAKE_RESULT, text)
    assert report.passed
    assert len(report.contradicted) == 0


def test_altered_irr_is_caught():
    text = "DECISION: INVEST. Decision score 69.2/100, confidence 81.7/100. IRR is 25.0%."
    report = validate_fidelity(FAKE_RESULT, text)
    assert not report.passed
    assert "IRR" in [c.label for c in report.contradicted]


def test_altered_decision_score_is_caught():
    """Regression test for the label-format bug found during build:
    'decision_score' vs 'decision score' mismatch let an altered score
    through undetected until fixed."""
    text = "DECISION: INVEST. Decision score 92.0/100, confidence 81.7/100. IRR is 12.9%."
    report = validate_fidelity(FAKE_RESULT, text)
    assert not report.passed
    assert "decision score" in [c.label for c in report.contradicted]


def test_altered_decision_state_fails_even_if_numbers_match():
    text = "DECISION: HOLD. Decision score 69.2/100, confidence 81.7/100. IRR is 12.9%."
    report = validate_fidelity(FAKE_RESULT, text)
    assert not report.decision_state_preserved
    assert not report.passed


def test_omitted_number_is_not_a_failure():
    """A number the explanation simply doesn't mention is fine -- omission
    is not the same as contradiction."""
    text = "DECISION: INVEST. Decision score 69.2/100, confidence 81.7/100."
    report = validate_fidelity(FAKE_RESULT, text)
    assert report.passed
    assert len(report.omitted) > 0


def test_currency_representation_accepts_lakh_crore_forms():
    text = "DECISION: INVEST. Decision score 69.2/100, confidence 81.7/100. NPV is 28.47 lakhs."
    report = validate_fidelity(FAKE_RESULT, text)
    assert "NPV" not in [c.label for c in report.contradicted]


# ------------------------------------------------------------ No API key path
def test_no_api_key_falls_back_immediately():
    with patch.dict(os.environ, {}, clear=True):
        result = generate_ai_explanation(REAL_INVEST_RESULT, api_key=None)
    assert result["source"] == "deterministic_fallback"
    assert "No GEMINI_API_KEY" in result["fallback_reason"]
    assert "INVEST" in result["explanation"]


# ------------------------------------------------------- Mocked LLM response
def test_faithful_llm_response_is_returned_as_is():
    d = REAL_INVEST_RESULT
    fake_llm_text = (
        f"DECISION: {d['decision']}. Decision score {d['decision_score']}/100, "
        f"confidence {d['decision_confidence']}/100. This property looks favorable."
    )
    with patch("ai_explanation_layer._call_gemini", return_value=fake_llm_text):
        result = generate_ai_explanation(d, api_key="fake-key-for-test")
    assert result["source"] == "llm"
    assert result["explanation"] == fake_llm_text
    assert result["fidelity_report"]["passed"] is True


def test_tampered_llm_response_is_discarded_and_falls_back():
    d = REAL_INVEST_RESULT
    tampered_score = round(d["decision_score"] + 20, 1)
    fake_llm_text = (
        f"DECISION: {d['decision']}. Decision score {tampered_score}/100, "
        f"confidence {d['decision_confidence']}/100. This property looks extremely favorable."
    )
    with patch("ai_explanation_layer._call_gemini", return_value=fake_llm_text):
        result = generate_ai_explanation(d, api_key="fake-key-for-test")
    assert result["source"] == "deterministic_fallback"
    assert "FAILED numeric fidelity validation" in result["fallback_reason"]
    assert str(tampered_score) not in result["explanation"]  # tampered text never shown to the user


def test_llm_response_overriding_decision_state_is_discarded():
    d = REAL_AVOID_RESULT
    fake_llm_text = (
        f"DECISION: INVEST. Decision score {d['decision_score']}/100, "
        f"confidence {d['decision_confidence']}/100. Actually I think you should invest anyway."
    )
    with patch("ai_explanation_layer._call_gemini", return_value=fake_llm_text):
        result = generate_ai_explanation(d, api_key="fake-key-for-test")
    assert result["source"] == "deterministic_fallback"
    assert d["decision"] in result["explanation"]  # correct decision (AVOID) still shown via fallback


def test_api_call_exception_falls_back_gracefully():
    def _raise(*a, **kw):
        raise TimeoutError("simulated network failure")
    with patch("ai_explanation_layer._call_gemini", side_effect=_raise):
        result = generate_ai_explanation(REAL_INVEST_RESULT, api_key="fake-key-for-test")
    assert result["source"] == "deterministic_fallback"
    assert "API call failed" in result["fallback_reason"]


def test_fallback_never_returns_empty_explanation():
    for d in (REAL_INVEST_RESULT, REAL_AVOID_RESULT):
        with patch.dict(os.environ, {}, clear=True):
            result = generate_ai_explanation(d, api_key=None)
        assert len(result["explanation"]) > 20


# ------------------------------------------------------- Post-delivery audit fix
def test_real_result_roi_protected_number_is_net_return_not_gross_multiple():
    """Regression test tied to the Phase 6 audit fix (engine.py
    compute_metrics), independently re-checked here because src/finance/
    was pulled into Phase 10B as a byte-identical copy of Phase 6's files
    and could silently regress to the pre-fix formula on a future re-copy.
    The numeric fidelity validator treats roi_total_holding_period as a
    PROTECTED number (correctly, per Master Prompt Section 10.10) -- but a
    validator that faithfully protects a WRONG value is worse than no
    validator at all, since it would actively defend a bug against
    correction. For property 2731 (5-year hold, ~17.85% IRR), total ROI
    must be well under 200% -- the pre-fix bug produced ~224% here."""
    roi = REAL_INVEST_RESULT["financial_findings"]["metrics"].get("roi_total_holding_period")
    assert roi is not None
    assert roi < 2.0, (
        f"roi_total_holding_period={roi} looks like the pre-fix gross-cash-multiple bug"
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
