"""
Phase 9, Section 9.3 (Standard Agent Contract) & 9.8 (Final DecisionResult)
===============================================================================
Every agent in this phase returns an `AgentFinding` -- never uncontrolled
prose as its only output (§9.3). The top-level pipeline assembles agent
findings into one `DecisionResult` (§9.8).
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Any


@dataclass
class AgentFinding:
    agent_name: str
    status: str                      # PASS / PASS WITH LIMITATIONS / CONDITIONAL / REJECTED /
                                      # BLOCKED / INSUFFICIENT DATA / UNCALIBRATED
    finding_type: str                # e.g. "property_facts", "market_snapshot", "valuation_prediction"
    summary: str                     # one-line, human-readable, built from structured data only
    metrics: dict = field(default_factory=dict)
    evidence_ids: list = field(default_factory=list)
    source: str = ""                 # which upstream module/phase produced this
    confidence: Optional[float] = None   # 0-100, this agent's own view of its output quality
    limitations: list = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw: Any = None                  # full underlying structured result, for downstream agents that need it

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)  # raw is for in-process use between agents; not for CSV/JSON export
        return d


@dataclass
class DecisionResult:
    property_id: int
    decision: str                    # INVEST / HOLD / AVOID / INSUFFICIENT
    decision_score: Optional[float]
    decision_confidence: Optional[float]
    market_findings: dict
    prediction_findings: dict
    financial_findings: dict
    risk_findings: dict
    geo_findings: dict
    evidence: dict
    key_reasons: list
    key_risks: list
    critical_assumptions: list
    conditions: list
    recommended_actions: list
    limitations: list
    data_quality_status: str
    model_status: str
    evidence_status: str
    component_scores: dict = field(default_factory=dict)
    gate_results: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)
