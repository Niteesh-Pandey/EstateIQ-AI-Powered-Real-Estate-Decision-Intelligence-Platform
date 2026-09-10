"""
Phase 5, Section 5.5 -- Semantic Retrieval (LSA)
====================================================
*** IMPORTANT TERMINOLOGY NOTE (Master Prompt Section 5.5) ***
"If LSA is used, describe it correctly as an offline semantic signal, not
as transformer embeddings."

This module implements Latent Semantic Analysis: TF-IDF vectorization
followed by Truncated SVD (a classical linear-algebra dimensionality
reduction, scikit-learn's TruncatedSVD). It captures co-occurrence-based
"topics" and can match a query to a document that shares no exact keywords
but similar term co-occurrence patterns. It is NOT a transformer/neural
embedding model (no BERT, no sentence-transformers, no contextual
attention) -- no such model was available in this environment (offline,
no network access for downloading pretrained weights). This is documented
here explicitly so no downstream consumer (Phase 9's Evidence Agent, or a
human reading the retrieval logs) mistakes LSA similarity for
transformer-embedding semantic similarity -- they have different failure
modes (LSA is a purely linear, corpus-statistics-based signal).

`ai.documents.embedding` (schema: `vector(384)`) is deliberately left
unpopulated by this phase -- see docs/evidence_report.md Limitations. It is
reserved for a genuine transformer-embedding model in a future phase; this
phase's semantic signal (LSA components, typically <=100) does not fit
that column and is stored/served separately.
"""
import os
import sys

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity

DEFAULT_N_COMPONENTS = 40  # capped below corpus size at fit time


class LSAIndex:
    def __init__(self, documents: list, n_components: int = DEFAULT_N_COMPONENTS, random_state: int = 42):
        self.doc_ids = [d["evidence_id"] for d in documents]
        texts = [d["content"] for d in documents]
        self.vectorizer = TfidfVectorizer(stop_words="english", min_df=1)
        tfidf = self.vectorizer.fit_transform(texts)
        n_comp = min(n_components, min(tfidf.shape) - 1) if min(tfidf.shape) > 1 else 1
        self.n_components_used = n_comp
        self.svd = TruncatedSVD(n_components=n_comp, random_state=random_state)
        self.doc_vectors = self.svd.fit_transform(tfidf)
        self.explained_variance_ratio = float(self.svd.explained_variance_ratio_.sum())

    def search(self, query: str, top_k: int = 10) -> list:
        q_tfidf = self.vectorizer.transform([query])
        q_vec = self.svd.transform(q_tfidf)
        sims = cosine_similarity(q_vec, self.doc_vectors)[0]
        order = np.argsort(-sims)[:top_k]
        return [(self.doc_ids[i], float(sims[i])) for i in order if sims[i] > 0]


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from evidence_registry import load_documents_from_csv, build_evidence_registry
    from chunking import chunk_evidence_registry

    chunks = chunk_evidence_registry(build_evidence_registry(load_documents_from_csv()))
    idx = LSAIndex(chunks)
    print(f"LSA components used: {idx.n_components_used}, "
          f"explained variance: {idx.explained_variance_ratio:.2%}")
    # Query using domain vocabulary but NO exact keyword overlap with any
    # single document title, to demonstrate the co-occurrence-based semantic
    # signal doing something pure keyword search would miss.
    query = "is this locality a good investment opportunity right now"
    results = idx.search(query, top_k=5)
    print(f"Query: '{query}'")
    for eid, score in results:
        doc = next(c for c in chunks if c["evidence_id"] == eid)
        print(f"  {eid}  sim={score:.3f}  {doc['title']}")
