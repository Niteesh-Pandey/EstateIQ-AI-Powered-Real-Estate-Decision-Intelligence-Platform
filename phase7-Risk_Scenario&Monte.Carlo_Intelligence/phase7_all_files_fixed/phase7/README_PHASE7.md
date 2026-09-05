# PHASE 7 — Risk, Scenario & Monte Carlo Intelligence
## Real Estate AI Decision Intelligence Platform

Follows Phase 6 in the Master A–Z Prompt's 10-phase architecture. Built directly on top of Phase 6's deterministic financial engine — **reused unchanged, never duplicated** (Master Prompt §7.2). Matches the established code-structure convention: live PostgreSQL via `db/connection.py`, `src/<topic>/*.py` modules, three orchestrators, an automated test suite.

## What was built

| Module | Purpose | Master Prompt Section |
|---|---|---|
| `monte_carlo.py` | Triangular-distribution Monte Carlo simulation (price, vacancy, opex, appreciation, interest rate), with a documented vacancy↔opex correlation. Every draw runs through Phase 6's `engine.run_financial_engine()` unchanged. | 7.3, 7.4 |
| `risk_metrics.py` | IRR/NPV/ROI distributions, probability of negative NPV/IRR, probability of meeting target IRR, VaR/CVaR at 95%/90%, downside percentiles, risk-driver ranking. | 7.5 |
| `decision_stability.py` | Financial-only INVEST/HOLD/AVOID classifier applied per simulated draw; measures how often the Base-case label survives simulation. **Not** Phase 9's authoritative decision policy — see docstring. | 7.8 |
| `scenario_engine.py` | Adds Severe Downside to Phase 6's Base/Upside/Downside. | 7.6 |
| `batch_runner_risk.py` | Runs the full pipeline across a demo sample (reuses Phase 6's property selection). | — |
| `export_results_csv.py` | 6 numbered CSVs → `docs/risk_results_csv/`. | 7.9 |
| `generate_charts.py` | 4 charts → `docs/risk_charts/`. | — |
| `test_phase7.py` | 21 automated tests (all passing, includes 1 post-delivery audit-fix regression test). | 7.10 |

Full detail: **`docs/phase7_report.md`**, **`docs/limitations.md`**.

## Notable finding

Across the entire n=25 demo batch, the **appreciation-rate assumption dominates simulated IRR risk** (mean correlation +0.999) far more than vacancy, opex, or purchase price. This is a structural consequence of Phase 6's low observed rental yields combined with a 5-year holding period — most of the return comes from the exit sale. It also means the Phase 6/Phase 3-documented unreliable-locality-appreciation issue (~14% of localities) matters more for this portfolio's risk than it might otherwise appear. Details in `docs/phase7_report.md` Section 6.

## Calibration status

**Every result in this phase is `UNCALIBRATED`.** No historical panel data exists in this dataset to fit distribution parameters or correlations against. Distribution bounds are documented judgement calls (see inline comments in `monte_carlo.py`), not statistically derived. Do not present these probabilities as real-world probabilities — see `docs/limitations.md` §1.

## How to run

### With a live database (production path)

```bash
cd phase7
pip install -r requirements-phase7.txt --break-system-packages
export DB_USER=...
export DB_PASSWORD=...

python3 src/risk/export_results_csv.py     # docs/risk_results_csv/*.csv
python3 src/risk/generate_charts.py        # docs/risk_charts/*.png
```

### Local re-check (no database — what was used to produce this deliverable)

```bash
cd phase7
pip install -r requirements-phase7.txt --break-system-packages

python3 src/risk/export_results_csv.py --source csv
python3 src/risk/generate_charts.py --source csv

python3 -m pytest src/risk/test_phase7.py -q
```

## Single-property example

```python
from src.finance.data_loader import load_property_financials_from_csv
from src.finance.engine import FinancialAssumptions
from src.risk.monte_carlo import run_monte_carlo, MonteCarloConfig
from src.risk.risk_metrics import compute_risk_metrics
from src.risk.decision_stability import compute_decision_stability
from src.risk.scenario_engine import run_extended_scenarios, extended_scenario_summary

observed = load_property_financials_from_csv(1)
assumptions = FinancialAssumptions(
    property_id=1,
    annual_operating_expenses=180000,
    vacancy_rate=0.05,
    appreciation_rate=0.08,
)

mc = run_monte_carlo(assumptions, observed, MonteCarloConfig(n_simulations=2000, seed=42))
risk = compute_risk_metrics(mc)
stability = compute_decision_stability(mc)
scenarios = extended_scenario_summary(run_extended_scenarios(assumptions, observed))
```
