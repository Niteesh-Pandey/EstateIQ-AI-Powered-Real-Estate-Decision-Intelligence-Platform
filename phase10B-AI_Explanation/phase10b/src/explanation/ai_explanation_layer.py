"""
Phase 10B, Section 10.10 -- AI Explanation Layer
=====================================================
"The LLM receives the structured DecisionResult and explains it. It may
explain: why the decision was made, positive factors, negative factors,
financial position, risk, location, evidence, conditions, recommended
actions. The LLM must preserve the actual underlying values. It cannot
change: IRR, NPV, ROI, risk score, decision score, decision state."

This module makes the real Gemini API call Phase 9's `explanation_agent.py`
deliberately did NOT make (see that module's docstring). Every explanation
this module returns has been run through `numeric_fidelity_validator.py`
BEFORE being handed back to the caller. If validation fails -- the LLM
altered a protected number -- this module does not return the LLM's text
at all. It falls back to Phase 9's deterministic template explanation and
says so explicitly, rather than silently shipping a demonstrably wrong
explanation.

No API key -> no live call is attempted, and the deterministic fallback is
used immediately with a clear reason -- same "never guess, report the gap"
governance pattern as every other phase's Missing Input Policy.

PROVIDER: Google Gemini (`generateContent` REST endpoint). Uses plain
`urllib` (no SDK dependency) for the same reason the rest of this platform
avoids unnecessary dependencies -- keeps `requirements-phase10b.txt`
minimal and this module trivially readable/auditable. The model name is
configurable via GEMINI_MODEL (default below) since Google's model
lineup changes faster than this codebase will -- check
https://ai.google.dev/gemini-api/docs/models for the current list before
relying on the default in production.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "agents"))

# Loads GEMINI_API_KEY / GEMINI_MODEL (and everything else) from a `.env`
# file at the project root, if one exists -- see .env.example. Real
# environment variables already set (e.g. by a deployment platform) always
# take priority over .env values.
load_dotenv(Path(_HERE).resolve().parent.parent / ".env")

from numeric_fidelity_validator import validate_fidelity
from explanation_agent import explain_decision as template_explain  # Phase 9's deterministic fallback

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.5-flash"  # override via GEMINI_MODEL env var if needed

SYSTEM_PROMPT = """You are the explanation layer of a real estate investment decision platform.

You will be given a structured DecisionResult (JSON) that was produced entirely by deterministic code: a financial engine, a Monte Carlo risk simulation, a geo-scoring engine, and a weighted decision policy. No part of the decision was made by you or any other LLM.

Your ONLY job is to explain this DecisionResult in clear business language: why the decision was made, the positive and negative factors, the financial position, the risk picture, the location factors, the evidence behind it, the conditions attached, and the recommended next actions.

HARD RULES, NON-NEGOTIABLE:
1. You MUST NOT change, round differently, recompute, or re-derive any number in the DecisionResult. If the IRR is 12.9%, you write "12.9%" -- not "approximately 13%", not "around 12-13%", not a recalculated figure.
2. You MUST NOT invent a number that is not present in the DecisionResult.
3. You MUST state the decision (INVEST/HOLD/AVOID/INSUFFICIENT) exactly as given, using that exact word.
4. You MUST NOT override, second-guess, or suggest a different decision than the one given. You explain the decision that was made, even if you would have decided differently.
5. If a value is null/None/"INSUFFICIENT DATA" in the input, say it is unavailable -- do not estimate or imply a value.
6. Write for a business reader: plain language, no jargon left unexplained, organized with clear sections (Decision, Why, Financial Position, Risk, Location, Evidence, Conditions, Recommended Actions).
7. Every specific number you state must be traceable to the DecisionResult you were given. When in doubt, omit a number rather than approximate it.
"""


def _call_gemini_raw(system_prompt: str, user_message: str, api_key: str) -> str:
    """Low-level Gemini call, generic over system prompt + user message.
    Both generate_ai_explanation() (decision explanations) and the Phase
    10B chat's general-question path (src/chat/general_qa.py) call this,
    so the actual API request/response handling exists in exactly one
    place."""
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    url = f"{GEMINI_API_BASE}/{model}:generateContent"
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "generationConfig": {"maxOutputTokens": 1200},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError(f"Gemini response contained no candidates: {data}")
    parts = candidates[0].get("content", {}).get("parts", [])
    text_blocks = [p["text"] for p in parts if "text" in p]
    return "\n".join(text_blocks)


def _call_gemini(decision_result: dict, api_key: str) -> str:
    user_message = f"Explain this DecisionResult:\n\n{json.dumps(decision_result, indent=2, default=str)}"
    return _call_gemini_raw(SYSTEM_PROMPT, user_message, api_key)


def generate_ai_explanation(decision_result: dict, api_key: str = None) -> dict:
    """Returns {"explanation": str, "source": "llm"|"deterministic_fallback",
    "fidelity_report": dict|None, "fallback_reason": str|None}."""
    api_key = api_key or os.environ.get("GEMINI_API_KEY")

    if not api_key:
        return {
            "explanation": template_explain(decision_result),
            "source": "deterministic_fallback",
            "fidelity_report": None,
            "fallback_reason": "No GEMINI_API_KEY available -- no LLM call attempted. Using Phase 9's "
                                "deterministic template rather than guessing at an explanation.",
        }

    try:
        llm_text = _call_gemini(decision_result, api_key)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as e:
        return {
            "explanation": template_explain(decision_result),
            "source": "deterministic_fallback",
            "fidelity_report": None,
            "fallback_reason": f"Gemini API call failed ({type(e).__name__}: {e}) -- falling back to the "
                                "deterministic template rather than returning no explanation at all.",
        }

    report = validate_fidelity(decision_result, llm_text)
    if not report.passed:
        contradicted_labels = [c.label for c in report.contradicted]
        return {
            "explanation": template_explain(decision_result),
            "source": "deterministic_fallback",
            "fidelity_report": _report_to_dict(report),
            "fallback_reason": f"LLM explanation FAILED numeric fidelity validation (altered: "
                                f"{contradicted_labels}, decision_state_preserved="
                                f"{report.decision_state_preserved}) -- discarded, falling back to the "
                                "deterministic template. The LLM output is never shown to the user "
                                "when it fails this check.",
        }

    return {
        "explanation": llm_text,
        "source": "llm",
        "fidelity_report": _report_to_dict(report),
        "fallback_reason": None,
    }


def _report_to_dict(report) -> dict:
    return {
        "passed": report.passed,
        "decision_state_preserved": report.decision_state_preserved,
        "n_protected_numbers": len(report.protected_numbers),
        "n_matched": len(report.matched),
        "n_contradicted": len(report.contradicted),
        "n_omitted": len(report.omitted),
        "contradicted_labels": [c.label for c in report.contradicted],
        "omitted_labels": [o.label for o in report.omitted],
    }


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "agents"))
    from orchestrator import run_decision_pipeline

    out = run_decision_pipeline(2731)
    result = generate_ai_explanation(out["decision_result"])
    print("Source:", result["source"])
    print("Fallback reason:", result["fallback_reason"])
    print()
    print(result["explanation"])
