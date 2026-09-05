# PHASE 9 — Multi-Agent Decision Intelligence
## Real Estate AI Decision Intelligence Platform

The integration phase: Phases 4-8 are wired into one controlled decision workflow that answers *"Should I invest in Property X?"* end-to-end. Matches the established convention: `src/<topic>/*.py` modules (all Phase 4-8 engines reused **unchanged**), orchestrators, numbered CSVs, charts, automated tests.

## What was built

**11 agents** in `src/agents/`, each returning a standard `AgentFinding`:

| Agent | Reuses (unchanged) |
|---|---|
| `query_understanding.py` | — (new, deterministic parsing) |
| `data_agent.py` | Phase 1 tables directly |
| `market_agent.py` | Phase 8's `_market_intelligence` + `_market_strength_score` |
| `prediction_agent.py` | Phase 4's `build_property_master` + trained models, respects READY/CONDITIONAL/REJECTED |
| `evidence_agent.py` | Phase 5's `HybridRetriever` + `rerank` |
| `finance_agent.py` | Phase 6's `run_financial_engine` + `run_scenarios` |
| `risk_agent.py` | Phase 7's `run_monte_carlo` + `compute_risk_metrics` + `compute_decision_stability` |
| `geo_agent.py` | Phase 8's `run_geo_engine` |
| `evidence_validator.py` | Phase 5's `grounding.validate_answer` |
| `decision_policy.py` | — (new, deterministic Decision Policy) |
| `explanation_agent.py` | — (new, deterministic template) |

`orchestrator.py` wires all of them into the full §9.9 flow and assembles the final `DecisionResult`. `test_phase9.py` — 37 automated tests, all passing (includes 1 post-delivery audit-fix regression test).

Full detail: **`docs/phase9_report.md`**, **`docs/limitations.md`**.

## Notable findings

Two real integration bugs were found and fixed while building this phase — both documented in detail in the report:
1. **Module name collisions** — Phases 6/7/8 each had a `data_loader.py`; combined in one process, Python silently returned the wrong one. Fixed with two filename-only renames.
2. **Evidence citation cross-contamination** — a text-joining bug caused citation markers to attach to the wrong document's numbers, which the Evidence Validator correctly caught as `BLOCKED`. Fixed, with a regression test locking it in.

All four decision states (INVEST, HOLD, AVOID, INSUFFICIENT) are confirmed reachable with real properties. Decision confidence is permanently capped below ~82/100 because Phase 7's risk simulation is permanently `UNCALIBRATED` — this is reported honestly, not hidden.

## How to run

```bash
cd phase9
pip install -r requirements-phase9.txt --break-system-packages

# Single property, full pipeline
python3 -c "
from src.agents.orchestrator import run_decision_pipeline
out = run_decision_pipeline('Should I invest in property 2731?', source='csv')
print(out['explanation'])
"

# Demo batch -> CSVs + charts
python3 src/agents/batch_runner_decision.py --source csv --n 25 --sims 1000
python3 src/agents/generate_charts.py --source csv --n 25 --sims 1000

# Tests
python3 -m pytest src/agents/test_phase9.py -q
```

With a live database, drop `--source csv` (defaults to `--source db`) and set `DB_USER`/`DB_PASSWORD`.

## Example output

```
DECISION: INVEST (property_id=2731)
Decision score: 69.2/100 | Decision confidence: 81.7/100

Key reasons:
  - Base-case IRR 12.9%, NPV ₹2,847,332 (5-year hold).
  - Locality 14: demand index 91.2, supply index 38.7, absorption rate 2.1 (as of 2025-12-01).
  - Location score 58.3/100.
  ...
```
