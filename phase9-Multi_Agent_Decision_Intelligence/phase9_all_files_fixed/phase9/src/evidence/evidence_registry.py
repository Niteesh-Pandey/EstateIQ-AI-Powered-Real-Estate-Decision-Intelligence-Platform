#!/usr/bin/env python
# coding: utf-8

# In[1]:


"""
Phase 5, Section 5.3 -- Evidence Registry
============================================
Builds the EvidenceRegistry: the trusted, structured record of every piece
of evidence available to the platform, sourced from `ai.documents`
(Phase 1 schema, sql/01_schema.sql lines 164-173).

Every EvidenceRegistry item carries exactly the fields the Master Prompt
requires (Section 5.3):
    evidence_id, source, title, content, metadata, source_type,
    confidence, as_of, created_at, document_id, chunk_id

PRODUCTION PATH (matches Phase 3's convention -- live PostgreSQL, no CSV
dependency): `load_documents_from_db()` queries `ai.documents` directly via
`db/connection.py`, exactly like Phase 3's `data_quality.py` / `insights.py`
query `core.*` tables. This is the path `generate_evidence_report.py` and
`export_results_csv.py` use when run against the user's local database.

DEV/TEST PATH: `load_documents_from_csv()` is a test-only convenience that
reads the identical rows from `data/processed/documents.csv` (the same file
that was originally loaded into `ai.documents` -- see Phase 1's loading
pipeline). It exists ONLY so this phase's own test suite
(`test_phase5.py`) can be independently re-checked in an environment
without a live PostgreSQL instance, WITHOUT changing the production
query path. It is never imported by `generate_evidence_report.py`.

Core rule (Master Prompt Section 5.12 / 3.2): if no evidence is found for a
query, retrieval returns an empty result -- this module never invents a
document, and never fabricates a field it cannot source from `ai.documents`.
"""
import os
import sys
from datetime import datetime, timezone

import pandas as pd

from pathlib import Path

# Go up 2 levels: evidence -> src -> phase5_all_files
BASE_DIR = Path(".").resolve().parents[1]  # Index 1 is the 2nd parent directory
CSV_PATH = BASE_DIR / "data" / "processed" / "documents.csv"

# Business rule: source-type quality tiers -> base confidence. Documented,
# not learned -- an internal research note and a market report are treated
# as higher-trust than a developer's own marketing filing (self-interested
# source) or a news snippet (secondhand, less granular). This mirrors the
# Master Prompt's "source quality" criterion used later in reranking
# (Section 5.6) and grounding (Section 5.7).
SOURCE_TYPE_MAP = {
    "Internal Research": ("INTERNAL_RESEARCH", 0.85),
    "Market Report": ("MARKET_REPORT", 0.80),
    "News": ("NEWS", 0.60),
    "Developer Filing": ("DEVELOPER_FILING", 0.55),
}
DEFAULT_SOURCE_TYPE, DEFAULT_CONFIDENCE = ("UNKNOWN", 0.40)


def _row_to_evidence(row: dict) -> dict:
    source_type, confidence = SOURCE_TYPE_MAP.get(row["source"], (DEFAULT_SOURCE_TYPE, DEFAULT_CONFIDENCE))
    title = f"{row['topic']} \u2014 {row['locality']}, {row['city']}"
    return {
        "document_id": int(row["document_id"]),
        "source": row["source"],
        "title": title,
        "content": row["text"],
        "metadata": {
            "city": row["city"],
            "locality": row["locality"],
            "topic": row["topic"],
        },
        "source_type": source_type,
        "confidence": confidence,
        "as_of": str(row["document_date"]),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def load_documents_from_db():
    """PRODUCTION PATH. Queries ai.documents on the live PostgreSQL database.
    Run with DB_USER / DB_PASSWORD set (see db/connection.py)."""
    sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "db"))
    from connection import get_cursor  # noqa: E402 (import located here to match Phase 3 module pattern)

    with get_cursor() as cur:
        cur.execute("""
            SELECT document_id, source, document_date, city, locality, topic, text
            FROM ai.documents
            ORDER BY document_id;
        """)
        rows = [dict(r) for r in cur.fetchall()]
    return [_row_to_evidence(r) for r in rows]


def load_documents_from_csv(path: str = CSV_PATH):
    """DEV/TEST PATH ONLY -- see module docstring. Not used by the
    production report/export scripts."""
    df = pd.read_csv(path)
    return [_row_to_evidence(r) for r in df.to_dict(orient="records")]


def build_evidence_registry(documents: list) -> list:
    """Assigns evidence_id/chunk_id at REGISTRY build time (pre-chunking,
    one evidence item per source document). chunking.py further splits
    `content` into chunk-level evidence items for retrieval -- see its
    docstring for why chunk_id=0 covers the whole document for this
    dataset's short document length."""
    registry = []
    for doc in documents:
        item = dict(doc)
        item["chunk_id"] = 0
        item["evidence_id"] = f"ev_{item['document_id']}_{item['chunk_id']}"
        registry.append(item)
    return registry


def registry_summary(registry: list) -> dict:
    if not registry:
        return {"n_evidence_items": 0}
    df = pd.DataFrame(registry)
    return {
        "n_evidence_items": len(df),
        "n_unique_documents": df["document_id"].nunique(),
        "by_source_type": df["source_type"].value_counts().to_dict(),
        "by_source": df["source"].value_counts().to_dict(),
        "mean_confidence": round(float(df["confidence"].mean()), 3),
        "date_range": [df["as_of"].min(), df["as_of"].max()],
    }


if __name__ == "__main__":
    docs = load_documents_from_csv()
    reg = build_evidence_registry(docs)
    print(registry_summary(reg))


# In[ ]:



