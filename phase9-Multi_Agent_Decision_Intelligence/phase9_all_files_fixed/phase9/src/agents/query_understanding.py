"""
Phase 9, Section 9.2 -- Query Understanding Agent
======================================================
Converts "Should I invest in Property X?" into structured intent:
property_id, objective, analysis_type, requested_outputs.

This is deliberately simple, deterministic parsing -- not an LLM call. The
platform's decision-critical path must not depend on an LLM correctly
extracting a property_id (Master Prompt §3.5: the LLM may explain/
summarize, never silently fill in decision-relevant inputs). If a property_id
cannot be found with confidence, this agent returns INSUFFICIENT rather than
guessing one.
"""
import re

import sys
import os


sys.path.insert(0, os.getcwd())
#sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contracts import AgentFinding

PROPERTY_ID_PATTERNS = [
    re.compile(r"property[_\s]?(?:id)?\s*[:#]?\s*(\d+)", re.IGNORECASE),
    re.compile(r"\bproperty\s+(\d+)\b", re.IGNORECASE),
    re.compile(r"^\s*(\d+)\s*$"),
]


def understand_query(query) -> AgentFinding:
    """`query` may be a plain int/str property_id, or a natural-language
    question containing one. Returns an AgentFinding whose `raw` field is
    the structured intent dict Phase 9's other agents consume."""
    property_id = None

    if isinstance(query, int):
        property_id = query
    elif isinstance(query, str):
        for pattern in PROPERTY_ID_PATTERNS:
            m = pattern.search(query.strip())
            if m:
                property_id = int(m.group(1))
                break

    if property_id is None:
        return AgentFinding(
            agent_name="QueryUnderstandingAgent", status="INSUFFICIENT DATA",
            finding_type="query_intent",
            summary=f"Could not extract a property_id from the query: {query!r}",
            source="query_understanding.py",
            confidence=0.0,
            limitations=["No property_id found in the query text. Provide either an integer property_id "
                         "or a sentence containing one (e.g. 'Should I invest in property 4021?')."],
        )

    intent = {
        "property_id": property_id,
        "objective": "investment_decision",
        "analysis_type": "single_property_full_evaluation",
        "requested_outputs": ["market_findings", "prediction_findings", "financial_findings",
                               "risk_findings", "geo_findings", "decision", "explanation"],
    }
    return AgentFinding(
        agent_name="QueryUnderstandingAgent", status="PASS",
        finding_type="query_intent",
        summary=f"Understood query as a full investment evaluation request for property_id={property_id}.",
        source="query_understanding.py",
        confidence=100.0,
        raw=intent,
    )


if __name__ == "__main__":
    print(understand_query("Should I invest in property 4021?").to_dict())
    print(understand_query(17).to_dict())
    print(understand_query("what a nice day").to_dict())

