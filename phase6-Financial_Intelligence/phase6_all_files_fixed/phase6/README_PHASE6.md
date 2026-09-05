# PHASE 6 — Financial Intelligence
## Real Estate AI Decision Intelligence Platform

Follows Phase 5 in the Master A–Z Prompt's 10-phase architecture. Matches the established code-structure convention from Phases 1/3/4/5 exactly: live PostgreSQL via `db/connection.py`, `src/<topic>/*.py` modules, three orchestrators (Markdown report, numbered CSV export, chart PNGs), and an automated test suite.

## What was built

| Module | Purpose | Master Prompt Section |
|---|---|---|
| `data_loader.py` | Sources every OBSERVED input (price, rent, expenses, vacancy, locality appreciation) from Phase 1 tables. Flags unreliable locality appreciation (inherited Phase 3 data bug). | 6.2 |
| `engine.py` | Deterministic cash-flow schedule, NOI, yields, cap rate, ROI, IRR, NPV, DSCR, cash-on-cash, payback, terminal CAGR. Implements the Missing Input Policy. | 6.3, 6.4, 6.7 |
| `scenarios.py` | Base / Upside / Downside + 6-driver sensitivity analysis. Reuses `engine.py` — no duplicated math. | 6.5, 6.6 |
| `batch_runner.py` | Reproducible demo sample selection + batch execution. | — |
| `export_results_csv.py` | 6 numbered CSVs → `docs/financial_results_csv/`. | 6.8 |
| `generate_charts.py` | 4 charts → `docs/finance_charts/`. | — |
| `test_phase6.py` | 25 automated tests (all passing, includes 2 post-delivery audit-fix regression tests). | 6.9 |

Full detail: **`docs/phase6_report.md`** (phase completion report), **`docs/limitations.md`**.

## Notable finding

Cross-checking historical price CAGR for all 90 localities found 13 (14.4%) with CAGRs above 30%/yr — up to 132.75%/yr — inherited from the Phase 3-documented data-generator compounding bug. The engine now refuses to use these as a default `appreciation_rate` and returns `INSUFFICIENT DATA` for that field instead, unless a caller explicitly overrides it. Details in `docs/phase6_report.md` Section 6.

## How to run

### With a live database (production path)

```bash
cd phase6
pip install -r requirements-phase6.txt --break-system-packages
export DB_USER=...
export DB_PASSWORD=...

python3 src/finance/export_results_csv.py     # docs/financial_results_csv/*.csv
python3 src/finance/generate_charts.py        # docs/finance_charts/*.png
```

### Local re-check (no database — what was used to produce this deliverable)

```bash
cd phase6
pip install -r requirements-phase6.txt --break-system-packages

python3 src/finance/export_results_csv.py --source csv
python3 src/finance/generate_charts.py --source csv

python3 -m pytest src/finance/test_phase6.py -q
```

## Single-property example

```python
from src.finance.data_loader import load_property_financials_from_csv
from src.finance.engine import FinancialAssumptions, FinancingTerms, run_financial_engine
from src.finance.scenarios import run_scenarios, run_sensitivity

observed = load_property_financials_from_csv(1)
assumptions = FinancialAssumptions(
    property_id=1,
    annual_operating_expenses=180000,   # supply if this property has no expense history
    vacancy_rate=0.05,
    appreciation_rate=0.08,
    financing=FinancingTerms(down_payment_pct=0.20, loan_interest_rate=0.09, loan_term_years=20),
)
result = run_financial_engine(assumptions, observed)
scenarios = run_scenarios(assumptions, observed)
sensitivity = run_sensitivity(assumptions, observed)
```
