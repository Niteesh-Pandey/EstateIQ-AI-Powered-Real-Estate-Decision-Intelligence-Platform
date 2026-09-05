#!/usr/bin/env python
# coding: utf-8

# In[2]:


"""
Phase 5, Section 5.5 -- Hybrid Retrieval
==========================================
Combines lexical (BM25) and semantic (LSA) scores into a single ranked
result, with optional metadata filtering (city/locality/topic/source_type/
date range). Both component scores are min-max normalized to [0,1] before
blending (raw BM25 and cosine-similarity scores are on different,
non-comparable scales -- blending them unnormalized would let whichever
happens to have larger magnitude dominate for the wrong reason).
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.getcwd())
from lexical_retrieval import BM25Index
from semantic_retrieval import LSAIndex

DEFAULT_LEXICAL_WEIGHT = 0.55
DEFAULT_SEMANTIC_WEIGHT = 0.45


def _minmax(scores: dict) -> dict:
    if not scores:
        return {}
    vals = np.array(list(scores.values()))
    lo, hi = vals.min(), vals.max()
    if hi - lo < 1e-9:
        return {k: 0.0 for k in scores}
    return {k: float((v - lo) / (hi - lo)) for k, v in scores.items()}


class HybridRetriever:
    def __init__(self, chunked_registry: list):
        self.registry = {item["evidence_id"]: item for item in chunked_registry}
        self.bm25 = BM25Index(chunked_registry)
        self.lsa = LSAIndex(chunked_registry)

    def _apply_filters(self, candidates: list, filters: dict) -> list:
        if not filters:
            return candidates
        out = []
        for eid in candidates:
            meta = self.registry[eid]["metadata"]
            item = self.registry[eid]
            ok = True
            for key in ("city", "locality", "topic"):
                if filters.get(key) and meta.get(key) != filters[key]:
                    ok = False
            if filters.get("source_type") and item.get("source_type") != filters["source_type"]:
                ok = False
            if filters.get("as_of_after") and item.get("as_of") < filters["as_of_after"]:
                ok = False
            if ok:
                out.append(eid)
        return out

    def retrieve(self, query: str, top_k: int = 10, filters: dict = None,
                 lexical_weight: float = DEFAULT_LEXICAL_WEIGHT,
                 semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
                 candidate_pool: int = 40) -> list:
        """Returns a ranked list of dicts: evidence_id, lexical_score,
        semantic_score, hybrid_score, plus the full evidence item."""
        lexical_hits = dict(self.bm25.search(query, top_k=candidate_pool))
        semantic_hits = dict(self.lsa.search(query, top_k=candidate_pool))

        all_ids = set(lexical_hits) | set(semantic_hits)
        all_ids = self._apply_filters(list(all_ids), filters or {})
        if not all_ids:
            return []  # Core Rule (5.12): no evidence -> empty result, never invented

        lex_norm = _minmax({eid: lexical_hits.get(eid, 0.0) for eid in all_ids})
        sem_norm = _minmax({eid: semantic_hits.get(eid, 0.0) for eid in all_ids})

        results = []
        for eid in all_ids:
            hybrid = lexical_weight * lex_norm.get(eid, 0.0) + semantic_weight * sem_norm.get(eid, 0.0)
            results.append({
                "evidence_id": eid,
                "lexical_score": round(lexical_hits.get(eid, 0.0), 4),
                "semantic_score": round(semantic_hits.get(eid, 0.0), 4),
                "hybrid_score": round(hybrid, 4),
                "evidence": self.registry[eid],
            })
        results.sort(key=lambda r: -r["hybrid_score"])
        return results[:top_k]


if __name__ == "__main__":
    from evidence_registry import load_documents_from_csv, build_evidence_registry
    from chunking import chunk_evidence_registry

    chunks = chunk_evidence_registry(build_evidence_registry(load_documents_from_csv()))
    retriever = HybridRetriever(chunks)

    print("Query: 'connectivity infrastructure Pune' (filtered to city=Pune)")
    for r in retriever.retrieve("connectivity infrastructure Pune", top_k=5, filters={"city": "Pune"}):
        e = r["evidence"]
        print(f"  {r['evidence_id']}  hybrid={r['hybrid_score']}  lex={r['lexical_score']}  "
              f"sem={r['semantic_score']}  {e['title']}")

    print("\nQuery: 'localities with no matching documents at all'")
    print(f"  results: {retriever.retrieve('xyzzy quux nonexistent term', top_k=5)}")


# In[ ]:



