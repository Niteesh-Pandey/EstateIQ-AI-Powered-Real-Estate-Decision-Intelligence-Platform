"""
Phase 9, Section 9.2 -- Explanation Agent
=============================================
"Converts the final structured decision into business-friendly language."

DESIGN CHOICE, stated explicitly: this agent is a deterministic Python
template, not an LLM call. Phase 10 (§10.10) is where an actual LLM
"AI Explanation Layer" belongs, reading the same DecisionResult this agent
produces. Building Phase 9's explanation as a template rather than an LLM
call keeps this phase's own test suite fully deterministic and keeps the
platform's decision-critical path free of any LLM dependency, per §3.5 ("the
LLM must not... modify calculations... override decision policy"). Every
number that appears in the generated text is read directly from the
DecisionResult, never re-stated from memory or rounded differently in two
places.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)


def explain_decision(decision_result: dict) -> str:
    d = decision_result
    lines = []

    lines.append(f"DECISION: {d['decision']} (property_id={d['property_id']})")
    if d["decision_score"] is not None:
        lines.append(f"Decision score: {d['decision_score']}/100 | "
                      f"Decision confidence: {d['decision_confidence']}/100")
    else:
        lines.append(f"Decision confidence: {d['decision_confidence']}/100 "
                      "(no decision score -- see limitations)")

    if d["key_reasons"]:
        lines.append("\nKey reasons:")
        lines.extend(f"  - {r}" for r in d["key_reasons"])

    if d["key_risks"]:
        lines.append("\nKey risks:")
        lines.extend(f"  - {r}" for r in d["key_risks"])

    if d["critical_assumptions"]:
        lines.append("\nCritical assumptions used:")
        lines.extend(f"  - {a}" for a in d["critical_assumptions"])

    if d["conditions"]:
        lines.append("\nConditions on this decision:")
        lines.extend(f"  - {c}" for c in d["conditions"])

    if d["recommended_actions"]:
        lines.append("\nRecommended next actions:")
        lines.extend(f"  - {a}" for a in d["recommended_actions"])

    if d["limitations"]:
        lines.append("\nLimitations:")
        lines.extend(f"  - {l}" for l in d["limitations"])

    lines.append(f"\nData quality: {d['data_quality_status']} | Model status: {d['model_status']} | "
                  f"Evidence status: {d['evidence_status']}")

    return "\n".join(lines)


if __name__ == "__main__":
    fake = {
        "property_id": 1, "decision": "HOLD", "decision_score": 52.3, "decision_confidence": 68.0,
        "key_reasons": ["Location score 51.7/100 is mid-range.", "IRR of 7.8% is below the 10% target."],
        "key_risks": ["83% simulated probability of negative NPV (UNCALIBRATED)."],
        "critical_assumptions": ["appreciation_rate=8%/yr assumed (locality data unreliable)."],
        "conditions": [], "recommended_actions": ["Re-negotiate purchase price or increase target rent."],
        "limitations": ["Risk simulation is UNCALIBRATED."],
        "data_quality_status": "PASS", "model_status": "PASS WITH LIMITATIONS", "evidence_status": "PASS",
    }
    print(explain_decision(fake))
