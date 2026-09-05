#!/usr/bin/env python
# coding: utf-8

# In[2]:


"""
Phase 5, Section 5.5 -- Lexical Retrieval (BM25)
====================================================
Implements Okapi BM25 from first principles (no extra dependency beyond
numpy -- keeps this phase's requirements file consistent with Phase 3's
minimal-dependency style). BM25 is a keyword/term-frequency ranking
function -- exact-word-match retrieval, complementary to the semantic
(LSA) signal in semantic_retrieval.py.
"""
import re
import math
from collections import Counter

import numpy as np

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list:
    return _TOKEN_RE.findall((text or "").lower())


class BM25Index:
    """Standard Okapi BM25 (k1=1.5, b=0.75 -- conventional defaults)."""

    def __init__(self, documents: list, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.doc_ids = [d["evidence_id"] for d in documents]
        self.tokenized_docs = [tokenize(d["content"]) for d in documents]
        self.doc_lengths = np.array([len(toks) for toks in self.tokenized_docs])
        self.avg_doc_len = float(self.doc_lengths.mean()) if len(self.doc_lengths) else 0.0
        self.n_docs = len(self.tokenized_docs)

        self.doc_freqs = []  # per-doc term counts
        df_counter = Counter()
        for toks in self.tokenized_docs:
            counts = Counter(toks)
            self.doc_freqs.append(counts)
            df_counter.update(counts.keys())
        self.idf = {
            term: math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))
            for term, df in df_counter.items()
        }

    def score(self, query: str) -> np.ndarray:
        q_tokens = tokenize(query)
        scores = np.zeros(self.n_docs)
        for i, (counts, dl) in enumerate(zip(self.doc_freqs, self.doc_lengths)):
            s = 0.0
            for term in q_tokens:
                if term not in counts:
                    continue
                idf = self.idf.get(term, 0.0)
                tf = counts[term]
                denom = tf + self.k1 * (1 - self.b + self.b * dl / (self.avg_doc_len or 1))
                s += idf * (tf * (self.k1 + 1)) / (denom or 1)
            scores[i] = s
        return scores

    def search(self, query: str, top_k: int = 10) -> list:
        scores = self.score(query)
        order = np.argsort(-scores)[:top_k]
        return [(self.doc_ids[i], float(scores[i])) for i in order if scores[i] > 0]


if __name__ == "__main__":
    import os
    import sys

    sys.path.insert(0, os.getcwd())
    from evidence_registry import load_documents_from_csv, build_evidence_registry
    from chunking import chunk_evidence_registry

    chunks = chunk_evidence_registry(build_evidence_registry(load_documents_from_csv()))
    idx = BM25Index(chunks)
    results = idx.search("infrastructure connectivity Pune", top_k=5)
    print("Query: 'infrastructure connectivity Pune'")
    for eid, score in results:
        doc = next(c for c in chunks if c["evidence_id"] == eid)
        print(f"  {eid}  score={score:.3f}  {doc['title']}")


# In[ ]:



