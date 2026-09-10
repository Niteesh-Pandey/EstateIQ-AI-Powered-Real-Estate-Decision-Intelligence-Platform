"""
Phase 5, Section 5.10 -- RAG Evaluation
==========================================
Tests the retrieval + grounding pipeline (NOT an LLM -- this platform's
Phase 5 deliverable is the retrieval/grounding layer; Phase 9/10 add the
LLM explanation layer on top) against six question categories:
  direct, paraphrased, ambiguous, no-answer, conflicting evidence, unsupported.

Because no LLM call is made here, "answer correctness" is evaluated at the
retrieval level: did the system surface (or correctly fail to surface) the
right evidence for each category? This is a legitimate, narrower evaluation
than full answer-quality grading, and is documented as such.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evidence_registry import load_documents_from_csv, build_evidence_registry
from chunking import chunk_evidence_registry
from hybrid_retrieval import HybridRetriever
from reranking import rerank


def build_test_pipeline():
    chunks = chunk_evidence_registry(build_evidence_registry(load_documents_from_csv()))
    return HybridRetriever(chunks), chunks


TEST_CASES = [
    # category, query, filters, expectation
    {"category": "direct", "query": "infrastructure connectivity score Shanker Gardens Pune",
     "filters": {"city": "Pune"}, "expect_nonzero": True,
     "expect_topic_contains": "Infrastructure"},
    {"category": "paraphrased", "query": "how well connected is Shanker Gardens in terms of roads and transit",
     "filters": {"city": "Pune"}, "expect_nonzero": True,
     "expect_topic_contains": None},
    {"category": "ambiguous", "query": "what about the market",
     "filters": None, "expect_nonzero": True, "expect_topic_contains": None},
    {"category": "no_answer", "query": "quantum blockchain metaverse yield farming",
     "filters": None, "expect_nonzero": False, "expect_topic_contains": None},
    {"category": "conflicting_evidence", "query": "policy regulatory outlook",
     "filters": {"topic": "Policy/Regulatory Note"}, "expect_nonzero": True,
     "expect_topic_contains": "Policy", "expect_multiple_sources": True},
    {"category": "unsupported", "query": "expected rental yield increase next decade prediction",
     "filters": None, "expect_nonzero": None,  # deliberately no strict expectation
     "expect_topic_contains": None},
]


def run_case(retriever, case: dict) -> dict:
    results = retriever.retrieve(case["query"], top_k=8, filters=case["filters"])
    reranked = rerank(case["query"], results)

    outcome = {"category": case["category"], "query": case["query"], "n_results": len(reranked)}

    if case["expect_nonzero"] is True:
        outcome["pass_nonzero"] = len(reranked) > 0
    elif case["expect_nonzero"] is False:
        outcome["pass_nonzero"] = len(reranked) == 0
    else:
        outcome["pass_nonzero"] = None  # no assertion for this category

    if case.get("expect_topic_contains"):
        topics = [r["evidence"]["metadata"]["topic"] for r in reranked[:5]]
        outcome["pass_topic"] = any(case["expect_topic_contains"] in t for t in topics)
        outcome["top_topics"] = topics
    else:
        outcome["pass_topic"] = None

    if case.get("expect_multiple_sources"):
        sources = {r["evidence"]["source"] for r in reranked}
        outcome["pass_multi_source"] = len(sources) > 1
        outcome["sources_seen"] = sorted(sources)
    else:
        outcome["pass_multi_source"] = None

    checks = [v for v in (outcome.get("pass_nonzero"), outcome.get("pass_topic"),
                           outcome.get("pass_multi_source")) if v is not None]
    outcome["overall_pass"] = all(checks) if checks else None
    return outcome


def run_evaluation() -> list:
    retriever, _ = build_test_pipeline()
    return [run_case(retriever, case) for case in TEST_CASES]


def evaluation_summary(results: list) -> dict:
    scored = [r for r in results if r["overall_pass"] is not None]
    return {
        "n_cases": len(results),
        "n_scored_cases": len(scored),
        "n_passed": sum(1 for r in scored if r["overall_pass"]),
        "pass_rate_pct": round(100 * sum(1 for r in scored if r["overall_pass"]) / len(scored), 1) if scored else None,
        "by_category": {r["category"]: r["overall_pass"] for r in results},
    }


if __name__ == "__main__":
    results = run_evaluation()
    for r in results:
        print(f"[{r['category']}] pass={r['overall_pass']}  n_results={r['n_results']}  query='{r['query']}'")
    print()
    print(evaluation_summary(results))
