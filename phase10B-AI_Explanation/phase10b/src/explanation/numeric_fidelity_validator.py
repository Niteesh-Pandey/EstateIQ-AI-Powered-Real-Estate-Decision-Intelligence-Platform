"""
Phase 10B, Section 10.10 -- Numeric Fidelity Validator
===========================================================
"The LLM must preserve the actual underlying values. It cannot change:
IRR, NPV, ROI, risk score, decision score, decision state."

This is the enforcement mechanism for that sentence. It is deterministic
Python, not another LLM call (Master Prompt §3.4: validation of a
calculation-adjacent output is itself a governance function, not
explanation, and must not be delegated to an LLM to grade itself).

Method: extract every "protected number" directly from the structured
DecisionResult (never from the LLM's text), extract every number the LLM's
explanation text actually states, and confirm each protected number that
appears in the explanation matches the source value within a small
rounding tolerance. A protected number that appears in the explanation
with a DIFFERENT value is a hard failure (the LLM altered a fact). A
protected number that simply doesn't appear in the explanation is not a
failure by itself (the LLM may reasonably omit a field) -- that is instead
reported as coverage, so a caller can see how much of the decision the
explanation actually addressed.

This mirrors Phase 5's grounding.validate_answer() in spirit (claims must
trace to a source) but is narrower and stricter: Phase 5 checks whether a
claim is *supported* by evidence; this checks whether a specific set of
already-known, already-correct numbers were *reproduced accurately* by a
downstream text generator that had no authority to change them.
"""
import re
from dataclasses import dataclass, field


# Decision-critical fields (Master Prompt §10.10's explicit list, plus the
# component scores the Decision Policy itself computed) -- every one of
# these is a "protected number." Percent-like fields are stored as their
# natural-language percentage representation (e.g. irr=0.129 -> "12.9").
PROTECTED_FIELD_PATHS = [
    ("decision_score", "decision score", "score"),
    ("decision_confidence", "decision confidence", "score"),
    ("financial_findings.metrics.irr", "IRR", "pct"),
    ("financial_findings.metrics.npv", "NPV", "currency"),
    ("financial_findings.metrics.cap_rate", "cap rate", "pct"),
    ("financial_findings.metrics.roi_total_holding_period", "ROI", "ratio_pct"),
    ("financial_findings.metrics.dscr", "DSCR", "score"),
    ("risk_findings.metrics.probability_negative_npv", "probability of negative NPV", "pct"),
    ("risk_findings.metrics.probability_meets_target_irr", "probability of meeting target IRR", "pct"),
    ("geo_findings.metrics.location_score", "location score", "score"),
    ("market_findings.metrics.market_strength_score", "market strength score", "score"),
]


@dataclass
class ProtectedNumber:
    field_path: str
    label: str
    raw_value: float
    representations: list  # acceptable numeric strings this value may appear as in text


@dataclass
class FidelityReport:
    decision_state_preserved: bool
    protected_numbers: list          # list[ProtectedNumber]
    numbers_found_in_text: list       # every numeric token the explanation actually contains
    matched: list                     # protected numbers correctly reproduced in the text
    contradicted: list                # protected numbers that appear ALTERED in the text (hard failure)
    omitted: list                     # protected numbers not mentioned at all (not a failure)
    passed: bool                      # True iff decision_state_preserved and contradicted == []


def _get_path(d: dict, path: str):
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur or cur[part] is None:
            return None
        cur = cur[part]
    return cur


def _representations(value: float, kind: str) -> list:
    """All the numeric-string forms a human (or LLM) might reasonably write
    this value as, so we don't false-flag a correct number just because of
    a formatting difference (e.g. 12.9 vs 12.90 vs 13)."""
    reps = set()
    if kind == "pct" or kind == "ratio_pct":
        pct = value * 100
        for nd in (0, 1, 2):
            reps.add(f"{pct:.{nd}f}")
        reps.add(f"{round(pct)}")
    elif kind == "currency":
        for nd in (0,):
            reps.add(f"{value:.{nd}f}")
        reps.add(f"{value:,.0f}".replace(",", ""))
        reps.add(f"{value/1e5:.2f}")   # lakhs
        reps.add(f"{value/1e7:.2f}")   # crores
        reps.add(f"{value/1e6:.2f}")   # millions
    else:  # plain score
        for nd in (0, 1, 2):
            reps.add(f"{value:.{nd}f}")
    return sorted(reps)


def extract_protected_numbers(decision_result: dict) -> list:
    protected = []
    for path, label, kind in PROTECTED_FIELD_PATHS:
        val = _get_path(decision_result, path)
        if val is None:
            continue
        protected.append(ProtectedNumber(field_path=path, label=label, raw_value=val,
                                          representations=_representations(val, kind)))
    return protected


_NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _numbers_in_text(text: str) -> list:
    found = []
    for m in _NUMBER_RE.finditer(text):
        cleaned = m.group().replace(",", "")
        found.append(cleaned)
    return found


def validate_fidelity(decision_result: dict, explanation_text: str) -> FidelityReport:
    protected = extract_protected_numbers(decision_result)
    text_numbers = _numbers_in_text(explanation_text)
    text_numbers_set = set(text_numbers)

    matched, contradicted, omitted = [], [], []
    for p in protected:
        if any(rep in text_numbers_set for rep in p.representations):
            matched.append(p)
        else:
            # Not found in its correct form -- check whether the label's
            # TOPIC is discussed at all with a DIFFERENT number nearby,
            # which would indicate an altered (not merely omitted) figure.
            label_mentioned = p.label.lower() in explanation_text.lower()
            if label_mentioned:
                contradicted.append(p)
            else:
                omitted.append(p)

    decision_state_preserved = decision_result.get("decision", "") in explanation_text

    passed = decision_state_preserved and not contradicted
    return FidelityReport(
        decision_state_preserved=decision_state_preserved,
        protected_numbers=protected, numbers_found_in_text=text_numbers,
        matched=matched, contradicted=contradicted, omitted=omitted, passed=passed,
    )


if __name__ == "__main__":
    fake_result = {
        "decision": "INVEST", "decision_score": 69.2, "decision_confidence": 81.7,
        "financial_findings": {"metrics": {"irr": 0.129, "npv": 2847332, "cap_rate": 0.041,
                                             "roi_total_holding_period": 1.62, "dscr": None}},
        "risk_findings": {"metrics": {"probability_negative_npv": 0.18, "probability_meets_target_irr": 0.82}},
        "geo_findings": {"metrics": {"location_score": 58.3}},
        "market_findings": {"metrics": {"market_strength_score": 61.0}},
    }
    good_text = "DECISION: INVEST. Decision score 69.2/100, confidence 81.7/100. IRR is 12.9%, NPV is ₹2,847,332."
    bad_text = "DECISION: INVEST. Decision score 92.0/100, confidence 81.7/100. IRR is 25.0%, NPV is ₹2,847,332."

    print("GOOD:", validate_fidelity(fake_result, good_text).passed)
    r = validate_fidelity(fake_result, bad_text)
    print("BAD:", r.passed, "contradicted:", [c.label for c in r.contradicted])
