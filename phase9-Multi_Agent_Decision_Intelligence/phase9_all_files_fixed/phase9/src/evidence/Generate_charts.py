#!/usr/bin/env python
# coding: utf-8

# In[9]:


"""
Phase 5 -- Chart Generator
============================
Matches Phase 3's docs/eda_charts/ convention (matplotlib PNGs saved
alongside the report). Run with --source csv for local re-check, --source
db for the live-database production path.
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


current_dir = os.getcwd()
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "..", "..", "db"))
OUT_DIR = os.path.join(current_dir, "..", "..", "docs", "evidence_charts")

#import os

#os.environ["DB_USER"] = "postgres"
#os.environ["DB_PASSWORD"] = "admin123"

main(source="csv")

import evidence_registry
import chunking
from hybrid_retrieval import HybridRetriever
from reranking import rerank
from observability import RetrievalLogger


def main(source="db"):
    os.makedirs(OUT_DIR, exist_ok=True)
    documents = (evidence_registry.load_documents_from_db() if source == "db"
                 else evidence_registry.load_documents_from_csv())
    registry = evidence_registry.build_evidence_registry(documents)
    chunked = chunking.chunk_evidence_registry(registry)
    df = pd.DataFrame(registry)

    # Chart 1: evidence items by source type
    fig, ax = plt.subplots(figsize=(7, 4.5))
    df["source_type"].value_counts().plot(kind="bar", ax=ax, color="#2c3e50")
    ax.set_title("Evidence Registry -- Items by Source Type")
    ax.set_xlabel("source_type")
    ax.set_ylabel("count")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "evidence_by_source_type.png"), dpi=120)
    plt.close(fig)

    # Chart 2: evidence items by topic
    fig, ax = plt.subplots(figsize=(7, 4.5))
    df["metadata"].apply(lambda m: m["topic"]).value_counts().plot(kind="barh", ax=ax, color="#34495e")
    ax.set_title("Evidence Registry -- Items by Topic")
    ax.set_xlabel("count")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "evidence_by_topic.png"), dpi=120)
    plt.close(fig)

    # Chart 3: retrieval latency across a demo query set
    retriever = HybridRetriever(chunked)
    logger = RetrievalLogger()
    demo_queries = [
        "infrastructure connectivity Pune", "developer track record",
        "policy regulatory outlook", "investment memo outlook Mumbai",
        "locality deep dive Hyderabad", "market outlook Bengaluru",
        "demand supply trend Chennai", "nonexistent gibberish query zzqx",
    ]
    for q in demo_queries:
        results = logger.timed_retrieve(retriever.retrieve, q, top_k=5)
        rerank(q, results)
    log_df = pd.DataFrame(logger.to_records())

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(range(len(log_df)), log_df["latency_ms"], color="#16a085")
    ax.set_xticks(range(len(log_df)))
    ax.set_xticklabels([q[:18] + ("..." if len(q) > 18 else "") for q in log_df["query"]],
                        rotation=45, ha="right", fontsize=8)
    ax.set_title("Retrieval Latency by Query (Hybrid BM25 + LSA)")
    ax.set_ylabel("latency (ms)")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "retrieval_latency.png"), dpi=120)
    plt.close(fig)

    # Chart 4: source-type mean confidence
    fig, ax = plt.subplots(figsize=(7, 4.5))
    df.groupby("source_type")["confidence"].mean().sort_values().plot(kind="barh", ax=ax, color="#8e44ad")
    ax.set_title("Mean Source Confidence by Source Type (documented tier map)")
    ax.set_xlabel("mean confidence")
    ax.set_xlim(0, 1)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "confidence_by_source_type.png"), dpi=120)
    plt.close(fig)

    print(f"Wrote 4 charts to {OUT_DIR}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["db", "csv"], default="db")
    args = parser.parse_args([])  # Pass [] to ignore Jupyter's internal connection flags
    main(source="csv")

# In[ ]:



