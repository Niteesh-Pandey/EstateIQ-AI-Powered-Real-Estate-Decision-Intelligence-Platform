# PHASE 8 — LIMITATIONS

*Consolidated from the phase report, per Master Prompt Section 16.*

## 1. No flood, environmental, or hazard data exists anywhere in this platform

Checked across Phase 1's full table set — no elevation data, no floodplain boundaries, no environmental monitoring readings, no climate-risk indicators of any kind. `geo_risk.compute_geo_risk()` therefore returns `flood_risk = {"status": "INSUFFICIENT DATA"}` and `environmental_risk = {"status": "INSUFFICIENT DATA"}` for **all 90 of 90 localities**, unconditionally — verified by a dedicated regression test across a spread of locality IDs. This is a genuine data gap in the source platform, not a limitation of this phase's logic; if a real hazard dataset becomes available, `data_loader.py` and `geo_risk.py` are the two places to wire it in.

## 2. Infrastructure coverage is sparse

209 infrastructure records across 90 localities (2.32 per locality on average). 65.6% of localities are missing at least one of the three tracked categories (transit, social, commercial), so their accessibility and infrastructure sub-scores are `PASS WITH LIMITATIONS` rather than `PASS` — the score is computed from whatever categories *are* present, with weights renormalized, rather than penalizing the missing categories as if they scored zero.

## 3. Location Score weights are a documented default, not a fitted model

`location_score.WEIGHTS` (connectivity 15%, safety 15%, infrastructure 15%, development 15%, commercial 10%, accessibility 15%, market strength 15%) reflect a business-judgement starting point. No historical investment-outcome dataset exists in this platform (e.g., "which localities actually performed best for investors") to fit these weights against. A real deployment should have the business explicitly review and, if desired, replace these before relying on the composite for investment decisions.

## 4. The distance-decay formula for accessibility is a simple, documented choice

`accessibility._proximity_weight(distance_km) = 1/(1+distance_km)` is monotonic and bounded but not fitted to any real travel-time, transit-frequency, or traffic data — none exists in this dataset. A more realistic model (e.g. actual transit travel times) would require external data this platform does not have.

## 5. Infrastructure delivery-risk and concentration-risk are proxy indicators

Both are computed directly from real `core.infrastructure` fields (`expected_completion`, `impact_score`), but they describe *this dataset's* infrastructure composition — they are not calibrated probabilities that any specific project will slip or that any specific locality will suffer a specific loss. This mirrors the honesty standard Phase 7 set for its Monte Carlo `UNCALIBRATED` status: a real number, honestly computed, but not a validated real-world probability.

## 6. `expected_completion` dates are taken at face value

No independent verification exists (in this platform) that a project marked "completed" (past `expected_completion`) was actually delivered on schedule, on budget, or as originally specified. The delivery-risk proxy can only measure *scheduling* status as recorded, not construction-quality or delivery-fidelity risk.

## 7. Market-strength normalization was fixed once during development — worth re-checking if source data changes

The original cap-based formula (ratio=1.0 → 100) saturated 78% of localities at the ceiling because this dataset's demand/supply ratios and absorption rates run structurally above 1.0. The fix uses P5/P95 anchors computed from the actual 90-locality distribution at build time. **If the underlying `market_monthly` data is regenerated or substantially changed**, these anchors (RATIO_P5=1.06, RATIO_P95=4.89, ABS_P5=0.48, ABS_P95=6.21, hardcoded in `location_score.py`) should be recomputed — they are data-driven constants, not universal ones, and the regression test (`test_market_strength_not_saturated_across_portfolio`) will catch re-saturation if they drift out of sync with new data.

## 8. No live PostgreSQL was available in this sandbox

Same situation as Phases 3, 5, 6, and 7. All orchestrators default to `--source db` (the production path) but were run here with `--source csv`, reading the identical rows Phase 1 loaded. Recommend re-running with `--source db` before Phase 9 integration.

## 9. City-level differentiation is weak in this composite

Mean Location Score by city ranges narrowly from 52.6 to 54.9 across all 6 cities — this dataset's city-level generation doesn't produce strong city-to-city separation in the composite. Locality-to-locality variation (37.6 to 70.5) is much more informative than city-to-city variation; a caller should not expect this score to answer "which city is best" with much confidence.
