"""
Phase 9, Section 9.3 (Standard Agent Contract) & 9.8 (Final DecisionResult)
===============================================================================
Every agent in this phase returns an `AgentFinding` -- never uncontrolled
prose as its only output (§9.3). The top-level pipeline assembles agent
findings into one `DecisionResult` (§9.8)."""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Any, List, Dict

@dataclass
class AgentFinding:
    agent_name: str
    status: str
    finding_type: str
    summary: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    evidence_ids: List[str] = field(default_factory=list)
    source: str = ""
    confidence: Optional[float] = None
    limitations: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw: Any = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d


@dataclass
class DecisionResult:
    property_id: int
    decision: str
    decision_score: Optional[float] = None
    decision_confidence: Optional[float] = None
    market_findings: Dict[str, Any] = field(default_factory=dict)
    prediction_findings: Dict[str, Any] = field(default_factory=dict)
    financial_findings: Dict[str, Any] = field(default_factory=dict)
    risk_findings: Dict[str, Any] = field(default_factory=dict)
    geo_findings: Dict[str, Any] = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)
    key_reasons: List[str] = field(default_factory=list)
    key_risks: List[str] = field(default_factory=list)
    critical_assumptions: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    data_quality_status: str = "UNKNOWN"
    model_status: str = "UNKNOWN"
    evidence_status: str = "UNKNOWN"
    component_scores: Dict[str, Any] = field(default_factory=dict)
    gate_results: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)