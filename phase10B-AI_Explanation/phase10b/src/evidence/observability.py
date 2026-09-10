"""
Phase 5, Section 5.9 -- Retrieval Observability
===================================================
Every retrieval call is logged with the fields the Master Prompt specifies:
query, filters, latency, result count, zero-result rate (computed at the
aggregate/session level), top source, evidence confidence.

Logs are appended in-memory during a run and can be flushed to CSV
(consumed by export_results_csv.py, same convention as Phase 3).
"""
import time
from datetime import datetime, timezone


class RetrievalLogger:
    def __init__(self):
        self.records = []

    def log_call(self, query: str, filters: dict, results: list, latency_seconds: float):
        top = results[0] if results else None
        self.records.append({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "query": query,
            "filters": filters or {},
            "latency_ms": round(latency_seconds * 1000, 2),
            "result_count": len(results),
            "zero_results": len(results) == 0,
            "top_evidence_id": top["evidence_id"] if top else None,
            "top_source": top["evidence"]["source"] if top else None,
            "top_confidence": top["evidence"].get("confidence") if top else None,
            "top_score": (top.get("rerank_score") or top.get("hybrid_score")) if top else None,
        })

    def timed_retrieve(self, retrieve_fn, query: str, filters: dict = None, **kwargs):
        """Wraps any retrieve callable (e.g. HybridRetriever.retrieve, or a
        retrieve+rerank pipeline) with a timer and auto-logs the call."""
        start = time.perf_counter()
        results = retrieve_fn(query, filters=filters, **kwargs) if filters is not None else retrieve_fn(query, **kwargs)
        elapsed = time.perf_counter() - start
        self.log_call(query, filters, results, elapsed)
        return results

    def summary(self) -> dict:
        if not self.records:
            return {"n_calls": 0}
        n = len(self.records)
        zero_count = sum(1 for r in self.records if r["zero_results"])
        latencies = [r["latency_ms"] for r in self.records]
        return {
            "n_calls": n,
            "zero_result_rate_pct": round(100 * zero_count / n, 1),
            "mean_latency_ms": round(sum(latencies) / n, 3),
            "p95_latency_ms": round(sorted(latencies)[int(0.95 * (n - 1))], 3),
            "mean_result_count": round(sum(r["result_count"] for r in self.records) / n, 2),
        }

    def to_records(self):
        return list(self.records)


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from evidence_registry import load_documents_from_csv, build_evidence_registry
    from chunking import chunk_evidence_registry
    from hybrid_retrieval import HybridRetriever
    from reranking import rerank

    chunks = chunk_evidence_registry(build_evidence_registry(load_documents_from_csv()))
    retriever = HybridRetriever(chunks)
    logger = RetrievalLogger()

    queries = [
        ("infrastructure connectivity Pune", {"city": "Pune"}),
        ("developer track record Mumbai", {"city": "Mumbai"}),
        ("nonexistent gibberish query zzqx", None),
        ("policy regulatory update", None),
    ]
    for q, f in queries:
        retrieved = logger.timed_retrieve(retriever.retrieve, q, filters=f, top_k=5)
        reranked = rerank(q, retrieved)
    print(logger.summary())
