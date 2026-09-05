# PHASE 7 — RISK, SCENARIO & MONTE CARLO INTELLIGENCE
## Real Estate AI Decision Intelligence Platform — Phase Completion Report

*Follows the Master A–Z Prompt's 10-phase architecture, Section 19 (Phase Completion Report). Matches the established convention: live PostgreSQL via `db/connection.py`, `src/<topic>/*.py` modules, orchestrators for Markdown report / numbered CSV export / charts, and an automated test suite.*

---

## 1. PHASE STATUS

**PHASE 7 — COMPLETE.** Monte Carlo simulation (§7.4), risk metrics (§7.5), decision stability (§7.8), and an extended Base/Downside/Severe Downside/Upside scenario set (§7.6) are built on top of Phase 6's **unchanged, reused** deterministic financial engine (§7.2). **21/21 automated tests passing** (20 original + 1 audit-fix regression test -- see Section 6B).

---

## 2. OBJECTIVE

Quantify uncertainty, downside risk, and decision stability (§7.1) for the same properties Phase 6 evaluated deterministically — without ever recomputing NOI, IRR, or NPV independently of Phase 6's engine.

---

## 3. SECTION 7.2 COMPLIANCE — HOW REUSE WAS ENFORCED, NOT JUST CLAIMED

`src/finance/engine.py`, `data_loader.py`, `scenarios.py`, and `batch_runner.py` are **byte-identical copies** of the Phase 6 deliverable's files (verified via `diff` before writing any Phase 7 code). Every Monte Carlo draw, every scenario stress point, every sensitivity point in this phase calls `engine.run_financial_engine()` — the exact same function Phase 6 tested 23 ways. Phase 7 adds *only*: (a) a way to generate many `FinancialAssumptions` from documented distributions, and (b) statistics over the resulting outputs. No NOI/IRR/NPV formula appears anywhere in `src/risk/`.

---

## 4. WHAT WAS BUILT

| Module | Master Prompt Section | Purpose |
|---|---|---|
| `monte_carlo.py` | 7.3, 7.4 | Triangular-distribution sampling for purchase price, vacancy, opex, appreciation, interest rate; a documented (not fitted) vacancy↔opex correlation via Gaussian copula; reproducible (seeded) simulation loop calling the Phase 6 engine per draw. |
| `risk_metrics.py` | 7.5 | IRR/NPV/ROI distributions, probability of negative NPV/IRR, probability of meeting target IRR, VaR₉₅/₉₀, CVaR₉₅/₉₀, downside percentiles, risk-driver ranking (correlation of each sampled input with simulated IRR). |
| `decision_stability.py` | 7.8 | A scoped, financial-only INVEST/HOLD/AVOID classifier applied to every simulated draw; measures how often the Base-case label survives simulation. |
| `scenario_engine.py` | 7.6 | Extends Phase 6's Base/Upside/Downside with a fourth, Severe Downside point — reusing `run_financial_engine` and Phase 6's `run_scenarios` directly. |
| `batch_runner_risk.py` | — | Runs the full risk pipeline across a demo sample (reuses Phase 6's `select_demo_sample` unchanged, so the same 25 properties are comparable across both phases). |
| `export_results_csv.py` | 7.9 | 6 numbered CSVs → `docs/risk_results_csv/`. |
| `generate_charts.py` | — | 4 charts → `docs/risk_charts/`. |
| `test_phase7.py` | 7.10 | 21 automated tests (all passing). |

---

## 5. WHY TRIANGULAR DISTRIBUTIONS, AND WHY THIS PHASE IS UNCALIBRATED (Section 7.7)

This dataset has no repeated-period panel for any single property (no time series of the same unit's vacancy, no multiple sales of the same unit to estimate price volatility from). There is therefore no defensible way to fit a Normal distribution's standard deviation from real historical outcomes — doing so would dress up a guess as a statistically-derived parameter, which is worse than being upfront about it. Every uncertain variable instead uses a **Triangular(min, mode=Base value, max)** distribution, where the min/max bounds are documented judgement calls (see `monte_carlo.DEFAULT_SPECS`, each with an inline comment explaining the reasoning for that range).

**`calibration_status = "UNCALIBRATED"` is attached to every `MonteCarloResult` this phase produces, with no exception.** Per §7.7: *"Never present synthetic/default Monte Carlo probabilities as real-world probabilities."* The probabilities in Section 7 below (e.g., "82.8% probability of negative NPV") describe what this simulation, run with these documented assumptions, produces — not a validated real-world likelihood.

One correlation is modeled: vacancy rate and operating expenses are drawn from a Gaussian copula with ρ=0.4 (a plausible business relationship — weak markets tend to show both — not fitted to this dataset, which has no panel data to fit it from). All other variables are sampled independently; no other correlation is claimed because none could be justified.

---

## 6. DEMO BATCH RESULTS (n=25, same properties as Phase 6, 2,000 simulations each, seed=42)

**Portfolio-level pattern — appreciation dominates risk.** Averaged across all 25 properties, the risk-driver ranking is:

| Driver | Mean correlation with simulated IRR |
|---|---|
| Appreciation rate | **+0.999** |
| Vacancy rate | -0.045 |
| Purchase price | -0.012 |
| Operating expenses | -0.026 |

This is not an artifact of the simulation code — it reflects the deal structure Phase 6 built: with a 5-year holding period and thin net rental yields (median 3.26%, from Phase 6), almost all of the return comes from the exit sale, which is driven almost entirely by the appreciation assumption. Annual operating variables (vacancy, opex) barely move the outcome by comparison. **This is itself a decision-relevant finding**: for this portfolio, an investor's real exposure is to the appreciation assumption, not operating execution — and Section 5's warning about the unreliable ~14% of localities (inherited from the Phase 3 data bug) is therefore more consequential here than it might first appear.

| Metric across the n=25 batch | Value |
|---|---|
| Base-case decision label distribution | INVEST: 17 · HOLD: 4 · AVOID: 4 |
| Mean simulated probability of negative NPV (at 10% discount rate) | 38.1% |
| Mean simulated probability of meeting target IRR | 61.9% |
| Mean decision stability (majority label matches Base label) | 84.9% (min 51.9%, max 100%) |
| Properties where Base label was the simulated minority (`unstable=True`) | **0 of 25** |

**Reading this honestly:** even though the mean probability of a negative NPV is 38%, the Base-case INVEST/HOLD/AVOID label was never overturned by the simulated majority for any of the 25 demo properties — the highest-uncertainty properties (e.g. property 5923: 100% probability of negative NPV) already had a Base-case label of HOLD or AVOID, not INVEST. See `docs/risk_charts/decision_stability_portfolio.png` for the full picture across the batch.

---

## 6B. POST-DELIVERY AUDIT FIX — inherited `roi_total_holding_period` bug (now fixed)

An independent review of this phase (following the same review that caught a bug in Phase 6) found that `src/finance/engine.py` here was copied from Phase 6 **before** Phase 6's own post-delivery audit fix — meaning this phase's `roi_total_holding_period` (a gross cash multiple, e.g. 223.8% instead of the correct 123.8% for property 2731's Base scenario) had silently carried the same bug into every Monte Carlo draw's ROI, `risk_metrics.roi_distribution`, and `05_extended_scenario_comparison.csv`.

**Fixed** by re-copying the corrected `engine.py` from Phase 6 (`roi = (total_return - equity_invested) / equity_invested`) — Section 3's "byte-identical copy, verified via diff" claim now holds against Phase 6's *current* (fixed) file, re-confirmed with `diff`. One new regression test was added directly to Phase 7's own suite (`test_roi_distribution_is_net_return_not_gross_multiple`) so this phase independently re-verifies the fix from its own Monte Carlo pipeline rather than only trusting Phase 6's tests — **suite is now 21/21 passing**. `docs/risk_results_csv/05_extended_scenario_comparison.csv` was regenerated with corrected values; no IRR, NPV, VaR, CVaR, probability, risk-driver, or decision-stability figure was affected (none of them depend on `roi_total_holding_period`).

---

## 7. TESTS EXECUTED / PASSED / FAILED

**21/21 passed** (20 original + 1 added during the post-delivery audit -- see Section 6B). Coverage: reproducibility (same seed → identical draws) and non-determinism across seeds; Monte Carlo correctly refusing to run on an unresolvable Base case; the `UNCALIBRATED` tag is always present; simulated mean IRR stays within 2 points of the Base-case point estimate (no systematic bias from the Triangular shocks); leverage measurably widens the IRR distribution; the vacancy/opex correlation is actually present in the drawn samples, not just configured; CVaR ≤ VaR at both 95% and 90% (a mathematical identity for a left-tail risk metric); all reported probabilities fall in [0,1]; the risk-driver ranking correctly identifies appreciation as dominant for this deal structure; the decision classifier's three branches (INVEST/AVOID/HOLD) are individually verified; decision-distribution percentages sum to 100%; an artificial base-vs-majority mismatch correctly sets `unstable=True`; and the four-point scenario ordering (Severe Downside ≤ Downside ≤ Base ≤ Upside) holds on both IRR and NPV.

---

## 8. MASTER PROMPT REQUIREMENTS COVERAGE

| Section | Requirement | Status |
|---|---|---|
| 7.2 | Reuse Phase 6's financial engine, no duplication | ✅ byte-identical copy, verified via diff |
| 7.3 | Uncertain variables: price, rent-adjacent (vacancy), expenses, appreciation, interest rate | ✅ `monte_carlo.DEFAULT_SPECS` |
| 7.4 | Distributions, sampling, correlation structure where justified, reproducibility, validation | ✅ `monte_carlo.py`, tested |
| 7.5 | IRR/NPV/ROI distributions, prob(negative NPV/return), prob(target return), VaR, CVaR, downside percentiles, risk drivers | ✅ `risk_metrics.py` |
| 7.6 | Base / Downside / Severe Downside / Upside | ✅ `scenario_engine.py` |
| 7.7 | UNCALIBRATED status, never present as real-world probability | ✅ enforced unconditionally in every result |
| 7.8 | Decision stability, only report values actually produced | ✅ `decision_stability.py`, scoped explicitly as financial-only |
| 7.9 | RiskResult / ScenarioResult / MonteCarloResult / RiskDrivers / DecisionStability outputs | ✅ all five present as structured dict outputs |
| 7.10 | Testing: distribution parameters, reproducibility, sample size, correlation, financial-engine integration, VaR, CVaR, scenario logic, decision stability | ✅ `test_phase7.py`, 21/21 |

---

## 9. BUSINESS VALUE

- Every Phase 6 point estimate now has an honest uncertainty band, not just a single number.
- VaR/CVaR give a concrete "how bad can this reasonably get" figure per property, usable directly in Phase 9's risk-completeness gate (§9.7).
- The risk-driver ranking tells a caller *which* assumption to interrogate hardest before committing — for this portfolio, consistently the appreciation assumption, which directly ties back to Phase 6's documented locality-reliability guard.
- Decision stability distinguishes a "confidently INVEST" property (e.g. property_id 2731: 100% stability, 0% probability of negative NPV) from a "marginal, could go either way" one (e.g. property_id 7622: 83.2% stability) — a distinction a single point estimate cannot make.

---

## 10. KNOWN LIMITATIONS (see also `docs/limitations.md`)

1. Distribution bounds and the one correlation modeled are documented judgement calls, not statistically fitted — `calibration_status = UNCALIBRATED` everywhere, unconditionally.
2. `holding_period_years` and `purchase_price`'s deeper negotiation dynamics are not treated as Monte Carlo variables in the default configuration (holding period is largely a decision choice, not a market uncertainty; purchase price gets only a narrow negotiation-range shock) — both are trivially extendable via `MonteCarloConfig.specs` if a caller wants to.
3. The decision-stability classifier is a **minimal, financial-only** placeholder — it is explicitly not Phase 9's authoritative DecisionPolicy (which will combine market/prediction/financial/risk/geo scores). Using this phase's INVEST/HOLD/AVOID label as if it were the final decision would be a governance violation of §9.4.
4. Same 44.5% OBSERVED-data coverage limitation as Phase 6 (see Phase 6 `docs/limitations.md` §4) — the demo batch only includes properties where this coverage bar is met.
5. No live PostgreSQL was available in this sandbox; run with `--source csv` (documented dev/test path). Recommend re-running with `--source db` (the default) against a live instance before Phase 9 integration.
6. Simulation runtime at full-portfolio scale (8,000 properties × 2,000 draws) was not measured; the n=25 demo batch (50,000 total engine calls) completed in a few seconds.

---

## 11. DEPENDENCIES

Phase 6 (`src/finance/engine.py`, `data_loader.py`, `scenarios.py`, `batch_runner.py`, reused unchanged). Transitively, Phase 1's `core.*` tables.

---

## 12. SECURITY CONSIDERATIONS

Unchanged from Phase 6: no hardcoded credentials, parameterized SQL, `DB_USER`/`DB_PASSWORD` required with no defaults.

---

## 13. PERFORMANCE CONSIDERATIONS

25 properties × 2,000 simulations × (1 unlevered financial-engine call per draw) = 50,000 engine calls, completing in a few seconds on this sandbox's single core. Not measured at full-portfolio scale; per §15, should be measured (not assumed) before any optimization decision.

---

## 14. PRODUCTION READINESS

Per Section 24: **Production-Oriented Prototype.** Monte Carlo, risk metrics, and decision-stability logic are complete, tested, and correctly labeled UNCALIBRATED. Recommended before Phase 9 integration: (a) re-run against a live PostgreSQL instance with `--source db`; (b) have the business explicitly review and, if desired, replace the documented Triangular bounds in `monte_carlo.DEFAULT_SPECS` with figures they're prepared to stand behind, since these numbers currently reflect this build's judgement calls, not the business's own risk appetite.

---

## 15. NEXT PHASE DEPENDENCIES

Phase 8 (Geo-Spatial & Location Intelligence) is independent of Phase 7 and may run in parallel (per the master architecture diagram). Phase 9's Risk Agent should call `risk_metrics.compute_risk_metrics()` and `decision_stability.compute_decision_stability()` directly rather than re-deriving anything, and must respect the `calibration_status = UNCALIBRATED` tag when computing decision confidence (§9.6) — an uncalibrated risk signal should reduce confidence, not be treated as equivalent to a validated one.

---

## 16. FINAL STATUS

**PHASE 7: COMPLETE.** Monte Carlo simulation, risk metrics (VaR/CVaR/probabilities/risk drivers), decision stability, and a four-point scenario set all built directly on Phase 6's unchanged financial engine — 21/21 automated tests passing (including 1 added during a post-delivery audit that caught an inherited Phase 6 ROI bug -- see Section 6B), calibration status honestly reported as UNCALIBRATED throughout, and one real portfolio-level insight surfaced (appreciation assumption dominates risk for this deal structure, tying back to the Phase 3/6-documented locality data-quality issue). Ready for Phase 8 (parallel) and Phase 9 integration.
