"""
Phase 5, Section 5.6 -- Reranking
===================================
Rerank hybrid-retrieval candidates using signals BEYOND raw text
similarity: source quality (confidence, from evidence_registry's documented
tier map), recency (as_of date), and query-term alignment (exact overlap
count, a lightweight explainability signal distinct from BM25's internal
scoring). Reranking never introduces a document that wasn't already
retrieved -- it only reorders/re-weights the existing candidate set
(Section 5.6 lists relevance/source quality/metadata/recency/query
alignment as inputs, not new retrieval).
"""
from datetime import datetime

import numpy as np

from lexical_retrieval import tokenize

RERANK_WEIGHTS = {
    "hybrid_score": 0.55,
    "source_confidence": 0.20,
    "recency": 0.15,
    "query_term_overlap": 0.10,
}
assert abs(sum(RERANK_WEIGHTS.values()) - 1.0) < 1e-9


def _recency_score(as_of: str, reference_date: str = None) -> float:
    """Linear decay: documents from the last 12 months score highest,
    documents older than 36 months score near zero. Bounded [0, 1]."""
    try:
        d = datetime.strptime(as_of[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return 0.5  # unknown date -> neutral, never invented as "recent"
    ref = datetime.strptime(reference_date[:10], "%Y-%m-%d") if reference_date else datetime.now()
    months_old = max(0.0, (ref - d).days / 30.44)
    return float(np.clip(1.0 - months_old / 36.0, 0.0, 1.0))


def _query_term_overlap(query: str, content: str) -> float:
    q_terms = set(tokenize(query))
    if not q_terms:
        return 0.0
    c_terms = set(tokenize(content))
    return len(q_terms & c_terms) / len(q_terms)


def _minmax_list(values):
    arr = np.array(values, dtype=float)
    lo, hi = arr.min(), arr.max()
    if hi - lo < 1e-9:
        return [0.0] * len(values)
    return list((arr - lo) / (hi - lo))


def rerank(query: str, retrieved: list, reference_date: str = None) -> list:
    """`retrieved` = output of HybridRetriever.retrieve(). Returns the same
    items, re-sorted, each annotated with rerank_score and its components."""
    if not retrieved:
        return []

    hybrid_scores = [r["hybrid_score"] for r in retrieved]
    hybrid_norm = _minmax_list(hybrid_scores)

    out = []
    for r, hs_norm in zip(retrieved, hybrid_norm):
        ev = r["evidence"]
        conf = ev.get("confidence", 0.4)
        rec = _recency_score(ev.get("as_of"), reference_date)
        overlap = _query_term_overlap(query, ev.get("content", ""))

        rerank_score = (
            RERANK_WEIGHTS["hybrid_score"] * hs_norm +
            RERANK_WEIGHTS["source_confidence"] * conf +
            RERANK_WEIGHTS["recency"] * rec +
            RERANK_WEIGHTS["query_term_overlap"] * overlap
        )
        item = dict(r)
        item.update({
            "rerank_score": round(float(rerank_score), 4),
            "source_confidence": conf,
            "recency_score": round(rec, 4),
            "query_term_overlap": round(overlap, 4),
        })
        out.append(item)

    out.sort(key=lambda r: -r["rerank_score"])
    return out


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from evidence_registry import load_documents_from_csv, build_evidence_registry
    from chunking import chunk_evidence_registry
    from hybrid_retrieval import HybridRetriever

    chunks = chunk_evidence_registry(build_evidence_registry(load_documents_from_csv()))
    retriever = HybridRetriever(chunks)
    query = "connectivity infrastructure Pune"
    retrieved = retriever.retrieve(query, top_k=10, filters={"city": "Pune"})
    reranked = rerank(query, retrieved)
    print(f"Query: '{query}' (reranked)")
    for r in reranked[:5]:
        e = r["evidence"]
        print(f"  {r['evidence_id']}  rerank={r['rerank_score']}  hybrid={r['hybrid_score']}  "
              f"conf={r['source_confidence']}  recency={r['recency_score']}  {e['source']}  {e['title']}")
