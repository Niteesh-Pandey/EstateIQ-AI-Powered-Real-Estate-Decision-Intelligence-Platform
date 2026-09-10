"""
Phase 9 -- Batch runner + numbered CSV export, matching the Phase 3/5/6/7/8
convention. Runs the FULL end-to-end decision pipeline (every agent, the
Decision Policy, and the Explanation Agent) across a demo sample of
properties -- reusing Phase 6's `select_demo_sample` for properties WITH
full OBSERVED financial data, plus a few known-sparse properties (e.g.
property 1) to demonstrate the INSUFFICIENT path honestly, not just PASS
cases.
"""
import argparse
import os
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "finance"))
from batch_runner import select_demo_sample  # reused from Phase 6, unchanged
from orchestrator import run_decision_pipeline

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "docs", "decision_results_csv")


def run_batch(n: int = 25, source: str = "csv", n_simulations: int = 1000, include_sparse: bool = True):
    ids = select_demo_sample(n, source=source)
    if include_sparse:
        ids = [1] + ids  # property 1: known to have no expense/rental history -> demonstrates INSUFFICIENT
    results = []
    for pid in ids:
        out = run_decision_pipeline(pid, source=source, n_simulations=n_simulations)
        results.append(out)
    return results


def build_tables(batch: list):
    summary_rows, component_rows, gate_rows, reasons_rows = [], [], [], []

    for out in batch:
        d = out["decision_result"]
        summary_rows.append({
            "property_id": d["property_id"], "decision": d["decision"],
            "decision_score": d["decision_score"], "decision_confidence": d["decision_confidence"],
            "data_quality_status": d["data_quality_status"], "model_status": d["model_status"],
            "evidence_status": d["evidence_status"],
        })
        for comp, score in d["component_scores"].items():
            component_rows.append({"property_id": d["property_id"], "component": comp, "score": score})
        for gate, passed in d["gate_results"].items():
            if gate != "all_passed":
                gate_rows.append({"property_id": d["property_id"], "gate": gate, "passed": passed})
        for r in d["key_reasons"]:
            reasons_rows.append({"property_id": d["property_id"], "type": "reason", "text": r})
        for r in d["key_risks"]:
            reasons_rows.append({"property_id": d["property_id"], "type": "risk", "text": r})

    return {
        "01_decision_summary": pd.DataFrame(summary_rows),
        "02_component_scores": pd.DataFrame(component_rows),
        "03_critical_gates": pd.DataFrame(gate_rows),
        "04_reasons_and_risks": pd.DataFrame(reasons_rows),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["csv", "db"], default="db")
    parser.add_argument("--n", type=int, default=25)
    parser.add_argument("--sims", type=int, default=1000)
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    batch = run_batch(n=args.n, source=args.source, n_simulations=args.sims)
    tables = build_tables(batch)
    for name, df in tables.items():
        path = os.path.join(OUT_DIR, f"{name}.csv")
        df.to_csv(path, index=False)
        print(f"Wrote {path} ({len(df)} rows)")

    decision_counts = tables["01_decision_summary"]["decision"].value_counts().to_dict()
    print("Decision distribution:", decision_counts)


if __name__ == "__main__":
    main()
