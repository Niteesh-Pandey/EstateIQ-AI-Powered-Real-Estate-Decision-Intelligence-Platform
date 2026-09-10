"""
Phase 9, Section 9.2 -- Evidence Validator
==============================================
"Before decision-making, validate: evidence existence, citation IDs,
grounding, source quality, evidence freshness where required, conflicts."

Reuses Phase 5's `grounding.validate_answer()` UNCHANGED -- runs it against
the Evidence Agent's own citation-marked summary and the real evidence
lookup table, exactly the module's intended use. If the Evidence Agent ever
produced a citation ID that doesn't exist in the registry, or a numeric
claim unsupported by the cited evidence, this validator catches it here,
before the Decision Policy runs -- matching the §9.9 flow (Evidence
Validator sits between Evidence/Finance/Risk/Geo Agents and the Decision
Policy).
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "evidence"))
from contracts import AgentFinding
from grounding import validate_answer  # reused from Phase 5, unchanged


def validate_evidence(evidence_finding: AgentFinding) -> AgentFinding:
    if evidence_finding.status == "INSUFFICIENT DATA" or not evidence_finding.raw:
        return AgentFinding(
            agent_name="EvidenceValidator", status="INSUFFICIENT DATA", finding_type="evidence_validation",
            summary="No evidence to validate -- Evidence Agent returned INSUFFICIENT DATA.",
            source="Phase 5 grounding.validate_answer (unchanged)", confidence=0.0,
        )

    evidence_lookup = evidence_finding.raw["evidence_lookup"]
    validation = validate_answer(evidence_finding.summary, evidence_lookup)

    hallucinated = validation["citation_id_check"].get("unknown_ids", [])
    unsupported_claims = validation["n_unsupported_claims"]
    coverage = validation["citation_coverage"]
    weak = validation["weak_grounding_flags"]

    status = validation["status"]  # BLOCKED / PASS WITH LIMITATIONS / PASS -- reused directly, not re-derived

    summary = (f"Evidence validation: {status}. "
               f"{len(hallucinated)} hallucinated citation IDs, "
               f"{unsupported_claims} unsupported numeric claims, "
               f"{len(coverage.get('uncited_numeric_sentences', []))} uncited numeric sentences, "
               f"{len(weak)} weak-grounding flags.")

    return AgentFinding(
        agent_name="EvidenceValidator", status=status, finding_type="evidence_validation",
        summary=summary,
        metrics={
            "n_hallucinated_citations": len(hallucinated),
            "n_unsupported_claims": unsupported_claims,
            "n_uncited_numeric_sentences": len(coverage.get("uncited_numeric_sentences", [])),
            "n_weak_grounding_flags": len(weak),
        },
        evidence_ids=evidence_finding.evidence_ids,
        source="Phase 5 grounding.validate_answer (unchanged)",
        confidence=100.0 if status == "PASS" else (50.0 if status == "PASS WITH LIMITATIONS" else 0.0),
        limitations=[f"Hallucinated citation IDs: {hallucinated}"] if hallucinated else [],
        raw=validation,
    )


if __name__ == "__main__":
    import os as _os
    _os.chdir(_os.path.dirname(_os.path.abspath(__file__)))
    from evidence_agent import get_evidence
    ef = get_evidence("Kakar Extension", "Delhi NCR")
    print(validate_evidence(ef).to_dict())
