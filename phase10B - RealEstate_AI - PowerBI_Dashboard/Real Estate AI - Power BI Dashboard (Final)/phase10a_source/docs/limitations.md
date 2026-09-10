# PHASE 10A — LIMITATIONS

*Consolidated from the phase report, per Master Prompt Section 16.*

## 1. No genuine `.pbix` file exists in this deliverable

This build environment has no Power BI Desktop and cannot produce a `.pbix` binary. What is delivered instead — governed data marts (`data_marts/*.csv`), data-accurate HTML dashboard mockups (`dashboards/*.html`), and a literal build guide with a DAX measures library (`docs/power_bi_architecture.md`) — is the honest substitute: everything a Power BI developer needs to produce the real file, reviewable by stakeholders before that work happens.

## 2. All 7 dashboards run on the n=26 demo batch, not the full 8,000-property portfolio

Every prior phase (6, 7, 9) built and tested its outputs against the same 25-property demo sample (properties with full expense+rental history) plus property 1 (added specifically to demonstrate the INSUFFICIENT path). These dashboards inherit that same sample rather than the full portfolio, for the same reason: full-portfolio financial/risk/decision evaluation was never run in any prior phase, so there is no governed full-portfolio output to source from. Dashboard 1's and Dashboard 5's KPIs that reference the full 8,000-property / 90-locality counts (from `properties.csv` / `localities.csv` directly) are the exception — those are simple counts, not evaluated outputs.

## 3. Dashboard rendering could not be fully screenshot-verified in this sandbox

The HTML dashboards load Chart.js and Google Fonts from CDNs (`cdnjs.cloudflare.com`, `fonts.googleapis.com`) for interactivity and typography. This sandbox's network egress allowlist does not include those domains, so this phase's own QA screenshots (via `wkhtmltoimage`) show the correct page structure, layout, tables, and KPI values, but not the actual charts or web font — those will render correctly in the person's own browser, which has normal internet access, but that was not directly observable here. The one real bug this QA process *did* catch (Section 5 of the phase report — property 1's missing locality name) was visible even without the charts rendering, which is what made it catchable at all.

## 4. The DAX measures library is documentation, not tested code

`docs/power_bi_architecture.md` Section 4 lists DAX formulas written for a real Power BI data model. No Power BI runtime exists in this environment to execute or syntax-check them. A developer implementing the real report should treat these as a starting reference, not copy-paste-and-trust code.

## 5. Refresh automation is a documented target only

Section 7 of the architecture doc lists a suggested refresh cadence per mart. No scheduling, pipeline, or automation exists in this deliverable to actually implement it.

## 6. Governance status columns must not be dropped by whoever builds the real Power BI report

Every mart preserves the exact status vocabulary from its source phase (`PASS`, `PASS WITH LIMITATIONS`, `CONDITIONAL`, `REJECTED`, `UNCALIBRATED`, `INSUFFICIENT DATA`). It would be easy, and wrong, for a Power BI developer optimizing for a "cleaner-looking" dashboard to collapse these into a single green/red indicator — doing so would erase exactly the honesty this platform has built through Phases 1-9. This is called out explicitly in the architecture doc (Section 6) so it isn't lost in translation to the real tool.

## 7. Dashboard 2's locality-level YoY/MoM growth is computed fresh in this phase, not copied from Phase 8

Phase 8 computed a locality-level appreciation CAGR (for the financial engine's use in Phase 6/7), but not a YoY/MoM price-growth figure formatted for a market dashboard. `build_market_locality_mart()` computes YoY/MoM directly from `core.market_monthly` — the same source table, same underlying values, different aggregation window than Phase 6/8's CAGR — so a reader comparing this dashboard's YoY growth figure to Phase 6's appreciation-rate assumption for the same locality should expect them to differ (different time windows, different purposes), not treat a mismatch as an error.

## 8. Post-delivery audit fix: inherited the Phase 6 ROI bug propagated further than in Phase 7/9 (now fixed)

`src/finance/engine.py`, and the static `sources/phase6/*.csv` / `sources/phase7/05_extended_scenario_comparison.csv` files this phase's mart builder reads, were all pulled in *before* Phase 6's own post-delivery audit fixed a bug in `roi_total_holding_period` (it was computing a gross cash multiple instead of a net return, overstating ROI by exactly 100 percentage points in every case -- the same inherited-stale-copy issue independently found in Phases 7 and 9). Unlike those two phases, here the bug reached the actual Power BI-facing data layer: `mart_04_financial_risk.csv` and `mart_04c_scenarios_extended4.csv` carried the wrong values (though no dashboard HTML visibly labels `roi_total_holding_period` as a rendered number -- only cap rate, IRR, NPV, DSCR, and Monte Carlo probabilities are shown). **Fixed** by re-copying Phase 6's corrected `engine.py` and the four affected source CSVs (property_id sets verified identical before substituting), then rerunning `build_marts.py` and all 7 dashboard-generation scripts. Portfolio KPIs and the decision distribution were independently re-derived from the regenerated marts and came back identical to what was already reported, confirming no decision-relevant figure was ever affected.

## 9. No automated test suite existed for this phase prior to audit (now added)

`src/marts/test_phase10a.py` (9 tests) was added during the same review -- this phase had inherited `test_phase6.py`/`test_phase8.py` from its source phases but had nothing testing the marts or dashboards it actually builds. All 9 passing; see Section 5B of `docs/phase10a_report.md` for what each test checks.
