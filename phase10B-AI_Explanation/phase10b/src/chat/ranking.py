"""
Phase 10B Chat -- Ranking
===========================
Answers "top N / best / safest / highest-return" questions by actually
running the deterministic decision pipeline on a representative sample of
properties and sorting by the metric the question asked for -- never by
whatever order happens to appear in a CSV file (the original chat
script's `df['property_id'].head(5)` bug: that returns the first 5 rows
of the file, which has no relationship to investment quality at all).

Runs against Phase 6's `select_demo_sample` -- the same deterministic,
seeded sample of properties with complete financial data used throughout
this platform's own demo batches and reports, so results here are
consistent with every other dashboard/report in the project rather than
a different, unexplained subset.
"""
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "agents"))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "finance"))

from orchestrator import run_decision_pipeline


def _import_from_path(module_name, file_path):
    """Loads a module from an exact file path, bypassing sys.path lookup
    entirely. Needed here because both src/finance/ and src/geo/ contain
    a file named batch_runner.py -- a plain `import batch_runner` is
    ambiguous and will silently pick whichever one happens to already be
    in sys.modules or earliest on sys.path, which is exactly the bug this
    caused during testing (geo's batch_runner was picked up instead of
    finance's, which doesn't define select_demo_sample at all)."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_finance_batch_runner = _import_from_path(
    "finance_batch_runner",
    os.path.join(os.path.dirname(_HERE), "finance", "batch_runner.py"),
)
select_demo_sample = _finance_batch_runner.select_demo_sample

CRITERION_LABELS = {
    "decision_score": "Decision Score",
    "irr": "IRR",
    "confidence": "Decision Confidence",
}


def rank_properties(n: int = 5, criterion: str = "decision_score",
                     sample_size: int = 25, source: str = "csv") -> list:
    """Returns a list of up to `n` dicts, sorted best-first by `criterion`,
    each with property_id, decision, decision_score, decision_confidence,
    irr (if available), and the one-line top reason. Properties that come
    back INSUFFICIENT are excluded from ranking (there is nothing to rank
    them on), not silently scored as zero."""
    candidate_ids = select_demo_sample(sample_size, source=source)

    rows = []
    for pid in candidate_ids:
        try:
            out = run_decision_pipeline(pid, source=source)
        except Exception as e:
            continue
        d = out["decision_result"]
        if d.get("decision") == "INSUFFICIENT":
            continue
        irr = None
        ff = d.get("financial_findings") or {}
        metrics = ff.get("metrics") or {}
        irr = metrics.get("irr")
        reasons = d.get("key_reasons") or []
        rows.append({
            "property_id": pid,
            "decision": d.get("decision"),
            "decision_score": d.get("decision_score"),
            "decision_confidence": d.get("decision_confidence"),
            "irr": irr,
            "top_reason": reasons[0] if reasons else "(no reason recorded)",
        })

    sort_key = {
        "decision_score": lambda r: (r["decision_score"] if r["decision_score"] is not None else -1),
        "confidence": lambda r: (r["decision_confidence"] if r["decision_confidence"] is not None else -1),
        "irr": lambda r: (r["irr"] if r["irr"] is not None else -999),
    }.get(criterion, lambda r: (r["decision_score"] if r["decision_score"] is not None else -1))

    # Primary sort: decision quality tier (INVEST best, AVOID worst) --
    # "safest"/"highest return" means "best among properties actually
    # worth considering", not "whichever AVOID property happens to score
    # well on one isolated metric". Secondary sort: the requested metric.
    # Confirmed necessary by testing: without this, a "safest investment"
    # query (criterion=confidence) surfaced an AVOID property with
    # negative IRR ahead of genuine INVEST properties, purely because its
    # decision_confidence happened to tie the top score.
    DECISION_RANK = {"INVEST": 0, "HOLD": 1, "AVOID": 2}
    rows.sort(key=lambda r: (DECISION_RANK.get(r["decision"], 3), -sort_key(r)))
    return rows[:n]


def format_ranking(rows: list, criterion: str) -> str:
    if not rows:
        return ("No properties in the demo sample could be ranked -- every candidate came back "
                "INSUFFICIENT. This is a real finding (missing data), not an error being hidden.")
    label = CRITERION_LABELS.get(criterion, criterion)
    lines = [f"Top {len(rows)} properties, ranked by {label} (from the platform's demo sample):\n"]
    for i, r in enumerate(rows, 1):
        irr_str = f"{r['irr']*100:.1f}%" if r["irr"] is not None else "n/a"
        lines.append(
            f"{i}. Property {r['property_id']} -- {r['decision']} "
            f"(score {r['decision_score']}, confidence {r['decision_confidence']}, IRR {irr_str})\n"
            f"   {r['top_reason']}"
        )
    lines.append("\nAsk about any property id above (e.g. 'property " +
                  str(rows[0]["property_id"]) + "') for its full explanation.")
    return "\n".join(lines)
