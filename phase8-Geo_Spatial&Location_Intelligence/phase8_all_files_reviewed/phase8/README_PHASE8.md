# PHASE 8 — Geo-Spatial & Location Intelligence
## Real Estate AI Decision Intelligence Platform

Follows Phase 5 in the Master A–Z Prompt's 10-phase architecture (runs in parallel with Phases 6/7 — all three depend only on Phase 1, not on each other; they integrate in Phase 9). Matches the established code-structure convention: live PostgreSQL via `db/connection.py`, `src/<topic>/*.py` modules, three orchestrators, an automated test suite.

**Scale note:** this phase operates at the **locality level (90 rows)**, not the property level (8,000 rows) — so every result covers the full portfolio, no demo sampling needed like Phases 6/7 used.

## What was built

| Module | Purpose | Master Prompt Section |
|---|---|---|
| `data_loader.py` | Sources every OBSERVED input (locality scores, infrastructure records, market history) from Phase 1 tables. | 8.2 |
| `accessibility.py` | Distance-weighted accessibility, infrastructure, and neighborhood-quality sub-scores from real infrastructure distances. | 8.4, 8.5, 8.6 |
| `geo_risk.py` | flood/environmental risk correctly `INSUFFICIENT DATA` (no such data exists); infrastructure delivery-risk and concentration-risk as documented proxy indicators. | 8.7 |
| `location_score.py` | 7-component weighted composite with documented weights and renormalization. | 8.8 |
| `geo_engine.py` | Top-level `GeoResult` orchestrator. | 8.9 |
| `batch_runner.py` | Runs the full 90-locality portfolio. | — |
| `export_results_csv.py` | 4 numbered CSVs → `docs/geo_results_csv/`. | — |
| `generate_charts.py` | 4 charts → `docs/geo_charts/`. | — |
| `test_phase8.py` | 26 automated tests (all passing). | — |

Full detail: **`docs/phase8_report.md`**, **`docs/limitations.md`**.

## Notable finding

`flood_risk` and `environmental_risk` are `INSUFFICIENT DATA` for all 90 of 90 localities — this platform has no hazard/climate data anywhere, and the engine correctly refuses to estimate a substitute rather than inventing one (Master Prompt §8.7). A real normalization bug was also found and fixed during development: the first version of the market-strength formula saturated 78% of localities at a perfect score because this dataset's demand/supply ratios run structurally above the assumed ceiling. Fixed with data-driven P5/P95 normalization anchors; locked in with a regression test. Details in `docs/phase8_report.md` Sections 5–6.

## How to run

### With a live database (production path)

```bash
cd phase8
pip install -r requirements-phase8.txt --break-system-packages
export DB_USER=...
export DB_PASSWORD=...

python3 src/geo/export_results_csv.py     # docs/geo_results_csv/*.csv
python3 src/geo/generate_charts.py        # docs/geo_charts/*.png
```

### Local re-check (no database — what was used to produce this deliverable)

```bash
cd phase8
pip install -r requirements-phase8.txt --break-system-packages

python3 src/geo/export_results_csv.py --source csv
python3 src/geo/generate_charts.py --source csv

python3 -m pytest src/geo/test_phase8.py -q
```

## Single-locality example

```python
from src.geo.geo_engine import run_geo_engine

result = run_geo_engine(locality_id=2, source="csv")
print(result["location_score"]["location_score"])
print(result["geo_risk"]["flood_risk"])            # INSUFFICIENT DATA -- honest, not invented
print(result["accessibility"]["accessibility_score"])
```
