"""
Phase 9, Section 9.2 -- Evidence Agent
==========================================
Responsible for evidence retrieval, evidence selection, citation
references, and grounding (§9.2). Reuses Phase 5's `HybridRetriever` and
`rerank()` UNCHANGED. This agent's "summary" text is built entirely from
retrieved evidence content plus explicit [ev_...] citation markers -- never
free-form LLM prose -- so it can itself be validated by the Evidence
Validator (Phase 5's `grounding.validate_answer`) before the Decision
Policy ever sees it.
"""
import os
import sys

_HERE = os.path.abspath("")
# Or: _HERE = os.getcwd()

#_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "evidence"))
from contracts import AgentFinding
from evidence_registry import load_documents_from_csv, build_evidence_registry  # reused, unchanged
from chunking import chunk_evidence_registry  # reused, unchanged
from hybrid_retrieval import HybridRetriever  # reused, unchanged
from reranking import rerank  # reused, unchanged

_CHUNKS = None  # built once, lazily, and cached across calls in one process


def _get_chunks():
    global _CHUNKS
    if _CHUNKS is None:
        _CHUNKS = chunk_evidence_registry(build_evidence_registry(load_documents_from_csv()))
    return _CHUNKS


def get_evidence(locality_name: str, city_name: str, top_k: int = 5) -> AgentFinding:
    if not locality_name and not city_name:
        return AgentFinding(
            agent_name="EvidenceAgent", status="INSUFFICIENT DATA", finding_type="evidence_summary",
            summary="No locality/city name available to search evidence for.",
            source="ai.documents", confidence=0.0,
        )

    chunks = _get_chunks()
    retriever = HybridRetriever(chunks)
    query = f"{locality_name} {city_name} real estate market outlook infrastructure demand"
    filters = {"locality": locality_name} if locality_name else {"city": city_name}

    results = retriever.retrieve(query, top_k=top_k, filters=filters)
    if not results:
        # Core Rule (§5.12): widen to city-level rather than fabricate locality-specific evidence
        results = retriever.retrieve(query, top_k=top_k, filters={"city": city_name} if city_name else None)

    if not results:
        return AgentFinding(
            agent_name="EvidenceAgent", status="INSUFFICIENT DATA", finding_type="evidence_summary",
            summary=f"No evidence found for {locality_name or city_name}.",
            source="ai.documents (Phase 5 hybrid retrieval)", confidence=0.0,
            limitations=["No matching evidence documents -- per Phase 5's Core Rule (§5.12), no evidence "
                         "was invented."],
        )

    ranked = rerank(query, results)[:top_k]

    # Build a citation-marked summary strictly from retrieved content -- one
    # sentence per top evidence item, each tagged with its evidence_id.
    #
    # BUG FOUND DURING BUILD (fixed here): grounding.split_sentences() splits
    # text right after "[.!?]\s+", so a naive "{content} [{evidence_id}]"
    # joined with a space put each citation marker at the START of the NEXT
    # block's sentence instead of the END of its own -- e.g. "...corridor.
    # [ev_17_0] Market Outlook for Yadav Hills...67.0." was parsed as ONE
    # sentence, so ev_17_0 got checked against the *next* document's numbers
    # and failed claim validation (BLOCKED). Fix: strip each content block's
    # own trailing period and re-terminate with "[{evidence_id}]." so the
    # citation marker sits INSIDE its own sentence's final punctuation,
    # keeping each block's numbers correctly paired with their own citation.
    lines = []
    evidence_ids = []
    for r in ranked:
        ev = r["evidence"]
        content = ev["content"].strip()
        if content.endswith((".", "!", "?")):
            content = content[:-1]
        lines.append(f"{content} [{ev['evidence_id']}].")
        evidence_ids.append(ev["evidence_id"])
    summary = " ".join(lines)

    avg_score = sum(r.get("rerank_score", r["hybrid_score"]) for r in ranked) / len(ranked)
    status = "PASS" if avg_score >= 0.3 else "PASS WITH LIMITATIONS"

    return AgentFinding(
        agent_name="EvidenceAgent", status=status, finding_type="evidence_summary",
        summary=summary,
        metrics={"n_evidence_items": len(ranked), "avg_rerank_score": round(avg_score, 4)},
        evidence_ids=evidence_ids,
        source="ai.documents (Phase 5 hybrid retrieval + reranking, unchanged)",
        confidence=round(min(100.0, avg_score * 150), 1),
        limitations=[] if status == "PASS" else ["Retrieved evidence has a below-threshold relevance "
                                                    "score -- treat with extra caution."],
        raw={"ranked": ranked, "evidence_lookup": {c["evidence_id"]: c for c in chunks}},
    )


if __name__ == "__main__":
    result = get_evidence("Kakar Extension", "Delhi NCR")
    print(result.summary)
    print(result.status, result.confidence, result.evidence_ids)
