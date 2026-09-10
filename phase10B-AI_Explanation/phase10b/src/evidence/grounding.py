"""
Phase 5, Section 5.7 -- Grounding
===================================
Validates that an LLM-generated answer is actually supported by the
evidence it cites. Three checks, per the Master Prompt:

  1. Citation ID Validation -- every [ev_x_y] marker in the answer must
     resolve to a real evidence_id that was actually retrieved for this
     query. Unknown IDs FAIL validation outright (a hallucinated citation
     is worse than no citation).
  2. Claim Validation -- numeric claims (prices, scores, percentages, dates)
     attached to a citation must actually appear (within a small tolerance)
     in the cited evidence's content. This catches the LLM citing a real
     document but then misquoting a number from it.
  3. Citation Coverage -- the fraction of answer sentences that carry at
     least one citation. Sentences with a numeric claim and NO citation are
     flagged separately as the highest-severity gap.

Weak Grounding Detection additionally flags sentences whose only citation
is to a low-confidence source (Section 5.7's fourth requirement).

This module operates purely on text + the evidence registry -- it does NOT
call an LLM. It is the deterministic gate an LLM-generated answer must pass
through before being shown to a user (Section 3.4: evidence gates must be
deterministic code, not LLM self-assessment).
"""
import re

CITATION_RE = re.compile(r"\[(ev_\d+_\d+)\]")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
LOW_CONFIDENCE_THRESHOLD = 0.55


def split_sentences(text: str) -> list:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if s.strip()]


def validate_citation_ids(answer: str, evidence_lookup: dict) -> dict:
    cited = set(CITATION_RE.findall(answer))
    unknown = sorted(c for c in cited if c not in evidence_lookup)
    return {
        "cited_ids": sorted(cited),
        "unknown_citation_ids": unknown,
        "all_citations_valid": len(unknown) == 0,
    }


def validate_claims(answer: str, evidence_lookup: dict, tolerance: float = 0.01) -> list:
    """For each sentence with both a citation and a number, check the number
    (or a value within `tolerance` relative difference) appears in the cited
    evidence content. Returns one record per (sentence, cited number).
    Numbers INSIDE citation markers themselves (e.g. the '1' and '0' in
    '[ev_1_0]') are excluded from claim extraction -- they are IDs, not
    factual claims."""
    records = []
    for sent in split_sentences(answer):
        cited_ids = [c for c in CITATION_RE.findall(sent) if c in evidence_lookup]
        sent_without_citations = CITATION_RE.sub("", sent)
        numbers = [float(n) for n in NUMBER_RE.findall(sent_without_citations)]
        if not cited_ids or not numbers:
            continue
        cited_text = " ".join(evidence_lookup[c]["content"] for c in cited_ids)
        cited_numbers = [float(n) for n in NUMBER_RE.findall(cited_text)]
        for num in numbers:
            supported = any(
                abs(num - cn) <= tolerance * max(abs(cn), 1.0) for cn in cited_numbers
            )
            records.append({
                "sentence": sent, "claimed_number": num,
                "cited_ids": cited_ids, "supported": supported,
            })
    return records


def citation_coverage(answer: str) -> dict:
    sentences = split_sentences(answer)
    if not sentences:
        return {"n_sentences": 0, "coverage_pct": 0.0, "uncited_numeric_sentences": []}
    cited_flags = [bool(CITATION_RE.search(s)) for s in sentences]
    uncited_numeric = [s for s, has_cite in zip(sentences, cited_flags)
                        if not has_cite and NUMBER_RE.search(s)]
    return {
        "n_sentences": len(sentences),
        "n_cited_sentences": sum(cited_flags),
        "coverage_pct": round(100 * sum(cited_flags) / len(sentences), 1),
        "uncited_numeric_sentences": uncited_numeric,
    }


def weak_grounding_detection(answer: str, evidence_lookup: dict) -> list:
    flagged = []
    for sent in split_sentences(answer):
        cited_ids = [c for c in CITATION_RE.findall(sent) if c in evidence_lookup]
        if not cited_ids:
            continue
        confidences = [evidence_lookup[c].get("confidence", 0.4) for c in cited_ids]
        if max(confidences) < LOW_CONFIDENCE_THRESHOLD:
            flagged.append({"sentence": sent, "cited_ids": cited_ids,
                             "max_source_confidence": max(confidences)})
    return flagged


def validate_answer(answer: str, evidence_lookup: dict) -> dict:
    """Single entry point combining all four checks into one grounding
    verdict. `status` follows the platform's standard status vocabulary."""
    id_check = validate_citation_ids(answer, evidence_lookup)
    claims = validate_claims(answer, evidence_lookup)
    coverage = citation_coverage(answer)
    weak = weak_grounding_detection(answer, evidence_lookup)

    unsupported_claims = [c for c in claims if not c["supported"]]

    if not id_check["all_citations_valid"] or unsupported_claims:
        status = "BLOCKED"
    elif coverage["uncited_numeric_sentences"] or weak:
        status = "PASS WITH LIMITATIONS"
    else:
        status = "PASS"

    return {
        "status": status,
        "citation_id_check": id_check,
        "claim_validation": claims,
        "n_unsupported_claims": len(unsupported_claims),
        "citation_coverage": coverage,
        "weak_grounding_flags": weak,
    }


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from evidence_registry import load_documents_from_csv, build_evidence_registry
    from chunking import chunk_evidence_registry

    chunks = chunk_evidence_registry(build_evidence_registry(load_documents_from_csv()))
    lookup = {c["evidence_id"]: c for c in chunks}
    real_doc = lookup["ev_1_0"]
    print("Evidence ev_1_0 content:", real_doc["content"])

    # Case 1: well-grounded answer (correct number, real citation)
    good = f"Shanker Gardens shows a connectivity score of 59.9 [ev_1_0]. This reflects strong momentum [ev_1_0]."
    # Case 2: hallucinated citation ID
    bad_id = f"Shanker Gardens shows a connectivity score of 59.9 [ev_9999_0]."
    # Case 3: real citation but WRONG number (misquote)
    bad_number = f"Shanker Gardens shows a connectivity score of 12.3 [ev_1_0]."
    # Case 4: numeric claim with no citation at all
    uncited = "Shanker Gardens shows a connectivity score of 59.9."

    for label, ans in [("well-grounded", good), ("hallucinated citation ID", bad_id),
                        ("misquoted number", bad_number), ("uncited claim", uncited)]:
        result = validate_answer(ans, lookup)
        print(f"\n[{label}] -> status={result['status']}")
        print(f"  unsupported_claims={result['n_unsupported_claims']}, "
              f"unknown_ids={result['citation_id_check']['unknown_citation_ids']}, "
              f"coverage={result['citation_coverage']['coverage_pct']}%")
