"""
Phase 10B -- Interactive Chat CLI
===================================
A terminal Q&A interface over the whole platform. This is a full rewrite
of an earlier draft that could only handle "give me info about a
property" and did so unreliably (it matched any bare 4-digit number as a
property_id -- misfiring on years/percentages/locality numbers -- ranked
"best/top" properties by raw CSV row order rather than any real metric,
had no path at all for general questions, and read a `"valid"` key that
`generate_ai_explanation()` does not return).

This version routes every question through `src/chat/query_router.py`
into one of five handled paths (property / compare / locality / ranking /
general), and refuses to guess -- rather than silently defaulting to some
property -- when a question doesn't clearly fit any of them.

Setup: see .env.example / README_PHASE10B.md. Works with or without
GEMINI_API_KEY set (falls back to Phase 9's deterministic template or the
platform's own documentation, respectively, and says so explicitly).
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "src", "agents"))
sys.path.insert(0, os.path.join(_HERE, "src", "explanation"))
sys.path.insert(0, os.path.join(_HERE, "src", "chat"))

from dotenv import load_dotenv
load_dotenv(os.path.join(_HERE, ".env"))

from orchestrator import run_decision_pipeline
from ai_explanation_layer import generate_ai_explanation
from query_router import classify
from ranking import rank_properties, format_ranking
from locality_lookup import resolve_locality, properties_in_locality, format_locality_summary
from general_qa import answer_general_question

SOURCE = "csv"  # matches every other phase's dev/re-check path; use "db" with a live PostgreSQL


def explain_property(property_id: int) -> str:
    out = run_decision_pipeline(property_id, source=SOURCE)
    result = generate_ai_explanation(out["decision_result"])

    header = f"[Property {property_id}] -- explanation source: {result['source']}"
    if result["fallback_reason"]:
        header += f"\n(Note: {result['fallback_reason']})"
    return f"{header}\n\n{result['explanation']}"


def handle_property(intent: dict) -> str:
    return explain_property(intent["property_id"])


def handle_compare(intent: dict) -> str:
    blocks = []
    for pid in intent["property_ids"]:
        try:
            out = run_decision_pipeline(pid, source=SOURCE)
            d = out["decision_result"]
            blocks.append(
                f"Property {pid}: {d.get('decision')} "
                f"(score {d.get('decision_score')}, confidence {d.get('decision_confidence')})"
            )
        except Exception as e:
            blocks.append(f"Property {pid}: could not be evaluated ({type(e).__name__}: {e})")
    summary = "\n".join(blocks)
    return (f"Comparison of {len(intent['property_ids'])} properties:\n\n{summary}\n\n"
            f"Ask about a single property id above for its full explanation.")


def handle_locality(intent: dict) -> str:
    if intent.get("locality_id") is not None:
        info = resolve_locality(locality_id=intent["locality_id"])
    else:
        # No numeric id given alongside "locality" -- try to pull a name
        # from the raw query (everything after the word "locality").
        import re
        m = re.search(r"locality\s+(?:in\s+|of\s+)?(.+)", intent["raw_query"], re.IGNORECASE)
        name_hint = m.group(1).strip(" ?.!") if m else None
        if not name_hint:
            return ("Please specify a locality id or name, e.g. 'locality 32' or "
                    "'locality Shanker Gardens'.")
        info = resolve_locality(name_hint=name_hint)

    prop_ids = properties_in_locality(info["locality_id"]) if info["found"] else []
    return format_locality_summary(info, prop_ids)


def handle_ranking(intent: dict) -> str:
    rows = rank_properties(n=intent["n"], criterion=intent["criterion"], source=SOURCE)
    return format_ranking(rows, intent["criterion"])


def handle_general(intent: dict) -> str:
    result = answer_general_question(intent["raw_query"])
    note = f"\n(Note: {result['fallback_reason']})" if result["fallback_reason"] else ""
    return f"{result['answer']}{note}"


def handle_unclear(intent: dict) -> str:
    return intent.get("reason", "I couldn't understand that question -- could you rephrase it?")


DISPATCH = {
    "PROPERTY": handle_property,
    "COMPARE": handle_compare,
    "LOCALITY": handle_locality,
    "RANKING": handle_ranking,
    "GENERAL": handle_general,
    "UNCLEAR": handle_unclear,
}


def answer(question: str) -> str:
    intent = classify(question)
    handler = DISPATCH[intent["intent"]]
    try:
        return handler(intent)
    except Exception as e:
        return f"Something went wrong while answering this ({type(e).__name__}: {e})."


def main():
    print("=" * 70)
    print("Real Estate AI Decision Intelligence Platform -- Chat")
    print("=" * 70)
    print("Ask me anything about this platform. Examples:")
    print("  - '2731'                                (explain one property)")
    print("  - 'compare 2731 and 5053'                (compare properties)")
    print("  - 'top 5 properties'                     (best by decision score)")
    print("  - 'safest investment'                    (best by confidence)")
    print("  - 'highest returns'                      (best by IRR)")
    print("  - 'locality 32'  or  'locality Shanker Gardens'")
    print("  - 'why were some ML models rejected?'    (general question)")
    print("  - 'what does UNCALIBRATED mean?'         (general question)")
    print("Type 'exit' or 'quit' to end.\n")

    while True:
        try:
            user_input = input("Ask a question: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if user_input.lower() in ("exit", "quit"):
            print("Goodbye.")
            break
        if not user_input:
            continue

        print("\n" + "-" * 70)
        print(answer(user_input))
        print("-" * 70 + "\n")


if __name__ == "__main__":
    main()
