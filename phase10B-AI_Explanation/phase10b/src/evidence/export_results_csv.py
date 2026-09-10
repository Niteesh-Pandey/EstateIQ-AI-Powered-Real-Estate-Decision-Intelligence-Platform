"""
Phase 5 -- Export analysis results as CSV files.
Runs every evidence module fresh (matching Phase 3's export_results_csv.py
convention) and writes each module's output as a separate numbered CSV
under docs/evidence_results_csv/, alongside the Markdown report.

Data source: --source db (default, live PostgreSQL) or --source csv
(dev/test-only local re-check -- see evidence_registry.py docstring).
"""
import argparse
import os
import sys
import pandas as pd

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "..", "..", "db"))
OUT_DIR = os.path.join(current_dir, "..", "..", "docs", "evidence_results_csv")
os.makedirs(OUT_DIR, exist_ok=True)

import evidence_registry
import chunking
from hybrid_retrieval import HybridRetriever
from reranking import rerank
from grounding import validate_answer
from prompt_injection import scan_evidence_registry
from observability import RetrievalLogger
import rag_evaluation


def save(df, name):
    path = os.path.join(OUT_DIR, name)
    df.to_csv(path, index=False)
    print(f"  wrote {name} ({len(df)} rows)")


def safe(func, label):
    try:
        return func()
    except Exception as e:
        print(f"[Warning] {label} skipped: {e}")
        return None


def main(source="db"):
    print(f"Exporting Phase 5 evidence analysis results to CSV (source={source})...")

    documents = safe(
        evidence_registry.load_documents_from_db if source == "db" else evidence_registry.load_documents_from_csv,
        "load_documents",
    )
    if not documents:
        print("No documents loaded -- aborting export.")
        return

    registry = evidence_registry.build_evidence_registry(documents)

    # 1. Evidence registry
    save(pd.DataFrame(registry).drop(columns=["metadata"]).assign(
        city=[r["metadata"]["city"] for r in registry],
        locality=[r["metadata"]["locality"] for r in registry],
        topic=[r["metadata"]["topic"] for r in registry],
    ), "01_evidence_registry.csv")

    # 2. Chunked registry + chunking summary
    chunked = chunking.chunk_evidence_registry(registry)
    save(pd.DataFrame(chunked).drop(columns=["metadata"]).assign(
        city=[r["metadata"]["city"] for r in chunked],
        locality=[r["metadata"]["locality"] for r in chunked],
        topic=[r["metadata"]["topic"] for r in chunked],
    ), "02_chunked_evidence.csv")
    save(pd.DataFrame([chunking.chunking_summary(chunked)]), "02_chunking_summary.csv")

    # 3. Retrieval + observability log (fixed demo query set, reproducible)
    retriever = safe(lambda: HybridRetriever(chunked), "HybridRetriever init")
    logger = RetrievalLogger()
    demo_queries = [
        ("infrastructure connectivity Pune", {"city": "Pune"}),
        ("developer track record", None),
        ("policy regulatory outlook", {"topic": "Policy/Regulatory Note"}),
        ("investment memo outlook Mumbai", {"city": "Mumbai"}),
        ("locality deep dive Hyderabad", {"city": "Hyderabad"}),
        ("nonexistent gibberish query zzqx", None),
    ]
    all_hits = []
    if retriever:
        for q, f in demo_queries:
            results = logger.timed_retrieve(retriever.retrieve, q, filters=f, top_k=10)
            reranked = rerank(q, results)
            for rank_pos, r in enumerate(reranked, start=1):
                e = r["evidence"]
                all_hits.append({
                    "query": q, "filters": str(f), "rank": rank_pos,
                    "evidence_id": r["evidence_id"], "lexical_score": r["lexical_score"],
                    "semantic_score": r["semantic_score"], "hybrid_score": r["hybrid_score"],
                    "rerank_score": r["rerank_score"], "source": e["source"],
                    "source_confidence": e["confidence"], "title": e["title"],
                })
    save(pd.DataFrame(all_hits), "03_retrieval_results.csv")
    save(pd.DataFrame(logger.to_records()), "03_retrieval_observability_log.csv")

    # 4. Grounding validation demo set
    lookup = {c["evidence_id"]: c for c in chunked}
    grounding_rows = []
    if lookup:
        from grounding import split_sentences
        sample_ids = list(lookup.keys())[:5]
        for sid in sample_ids:
            first_sentence = split_sentences(lookup[sid]["content"])[0].rstrip(".")
            for label, ans in [
                ("well_grounded", f"{first_sentence} [{sid}]."),
                ("hallucinated_citation", f"{first_sentence} [ev_999999_0]."),
                ("uncited_claim", f"{first_sentence}."),
            ]:
                result = safe(lambda a=ans: validate_answer(a, lookup), f"grounding[{sid}][{label}]")
                if result:
                    grounding_rows.append({
                        "sample_evidence_id": sid, "case": label, "status": result["status"],
                        "n_unsupported_claims": result["n_unsupported_claims"],
                        "unknown_citation_ids": str(result["citation_id_check"]["unknown_citation_ids"]),
                        "coverage_pct": result["citation_coverage"]["coverage_pct"],
                    })
    save(pd.DataFrame(grounding_rows), "04_grounding_validation.csv")

    # 5. Prompt injection scan
    flags = safe(lambda: scan_evidence_registry(chunked), "prompt_injection_scan") or []
    save(pd.DataFrame(flags) if flags else pd.DataFrame(columns=["evidence_id", "document_id", "source", "hits"]),
         "05_prompt_injection_flags.csv")

    # 6. RAG evaluation
    eval_results = safe(rag_evaluation.run_evaluation, "rag_evaluation") or []
    save(pd.DataFrame(eval_results), "06_rag_evaluation.csv")

    print("Export complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["db", "csv"], default="db")
    args = parser.parse_args()
    main(source=args.source)
