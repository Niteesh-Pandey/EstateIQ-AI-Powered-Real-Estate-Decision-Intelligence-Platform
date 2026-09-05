#!/usr/bin/env python
# coding: utf-8

# In[2]:


"""
Phase 5, Section 5.4 -- Chunking
==================================
Splits each evidence item's `content` into retrieval-sized chunks, preserving
source and document relationships (chunk -> parent document_id).

Dataset-specific note: `ai.documents.text` in this platform averages ~221
characters (min 211, max 232 -- see Phase 3 EDA-style profiling in
export_results_csv.py output `01_evidence_registry.csv`). At the default
CHUNK_SIZE_CHARS=800, every document in this dataset fits inside a single
chunk, so chunking is a documented no-op here (1 chunk per document) --
NOT because chunking wasn't implemented, but because the current document
length doesn't require splitting. The sentence-boundary splitter below is
exercised and unit-tested (test_phase5.py) against a synthetic long
document to prove it behaves correctly once documents grow past the
threshold (e.g. full market reports ingested in a future phase).
"""
import re

CHUNK_SIZE_CHARS = 800
CHUNK_OVERLAP_CHARS = 120

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_into_sentences(text: str) -> list:
    text = (text or "").strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list:
    """Sentence-aware chunker: packs whole sentences into a chunk until
    chunk_size would be exceeded, then starts a new chunk carrying the last
    `overlap` characters forward for context continuity. Never splits a
    sentence mid-word."""
    sentences = split_into_sentences(text)
    if not sentences:
        return []

    chunks, current = [], ""
    for sent in sentences:
        candidate = f"{current} {sent}".strip() if current else sent
        if len(candidate) > chunk_size and current:
            chunks.append(current)
            # carry trailing `overlap` chars of the previous chunk forward
            tail = current[-overlap:] if overlap < len(current) else current
            current = f"{tail.strip()} {sent}".strip()
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def chunk_evidence_registry(registry: list, chunk_size: int = CHUNK_SIZE_CHARS,
                             overlap: int = CHUNK_OVERLAP_CHARS) -> list:
    """Expands a document-level EvidenceRegistry into a chunk-level one.
    Preserves every source field; only `content`, `chunk_id`, `evidence_id`
    change per chunk. `document_id` is retained on every chunk so the
    document relationship (Section 5.4: 'document relationships') is never
    lost."""
    chunked = []
    for item in registry:
        pieces = chunk_text(item["content"], chunk_size, overlap)
        if not pieces:
            continue
        for i, piece in enumerate(pieces):
            chunk_item = dict(item)
            chunk_item["content"] = piece
            chunk_item["chunk_id"] = i
            chunk_item["evidence_id"] = f"ev_{item['document_id']}_{i}"
            chunk_item["n_chunks_in_document"] = len(pieces)
            chunked.append(chunk_item)
    return chunked


def chunking_summary(chunked_registry: list) -> dict:
    import pandas as pd
    if not chunked_registry:
        return {"n_chunks": 0}
    df = pd.DataFrame(chunked_registry)
    return {
        "n_chunks": len(df),
        "n_source_documents": df["document_id"].nunique(),
        "mean_chunks_per_document": round(len(df) / df["document_id"].nunique(), 3),
        "max_chunks_in_a_document": int(df["n_chunks_in_document"].max()),
        "mean_chunk_length_chars": round(df["content"].str.len().mean(), 1),
    }


if __name__ == "__main__":
    from evidence_registry import load_documents_from_csv, build_evidence_registry
    reg = build_evidence_registry(load_documents_from_csv())
    chunked = chunk_evidence_registry(reg)
    print(chunking_summary(chunked))

    # Prove the splitter itself works on a document long enough to require
    # multiple chunks (synthetic, for demonstration only -- not real data).
    long_doc = " ".join([f"This is sentence number {i} describing a hypothetical long market report." for i in range(60)])
    pieces = chunk_text(long_doc, chunk_size=300, overlap=50)
    print(f"Synthetic long-document test: {len(long_doc)} chars -> {len(pieces)} chunks "
          f"(sizes: {[len(p) for p in pieces]})")


# In[ ]:



