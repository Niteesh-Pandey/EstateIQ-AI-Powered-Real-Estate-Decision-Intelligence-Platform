"""
Phase 10A -- Automated Tests
==============================
No test suite existed for this phase prior to post-delivery audit review.
Added here to close that gap (Master Prompt Section 12: "Implement testing
at every layer") and to lock in the two real issues the audit/build process
found: (1) an inherited Phase 6 ROI bug in the underlying source CSVs,
(2) the property_id=1 NaN-locality-name join gap the phase's own visual QA
already caught and fixed.

Run with: python3 test_phase10a.py
"""
import os
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
MARTS = os.path.join(os.path.dirname(_HERE), "..", "data_marts")
SOURCES = os.path.join(os.path.dirname(_HERE), "..", "sources")


# --------------------------------------------------------------- mart_04 (Financial & Risk)

def test_mart04_roi_is_net_return_not_gross_multiple():
    """Regression test tied to the Phase 6 audit fix: roi_total_holding_period
    must be a NET return, not a gross cash multiple. Checked here at the
    data-mart level (not just Phase 6's own tests) because this mart is
    built from a STATIC copy of Phase 6's source CSV under sources/phase6/,
    which can silently go stale on a future re-copy even if Phase 6's own
    code and tests are fine."""
    df = pd.read_csv(os.path.join(MARTS, "mart_04_financial_risk.csv"))
    row = df[df["property_id"] == 2731].iloc[0]
    # Sanity bound: for a 5-year hold with a double-digit annual IRR, total
    # ROI should be well under 3.0 (300%) -- the pre-fix bug produced 2.2377
    # (223.8%) for this exact property, which is what this bound catches.
    assert row["roi_total_holding_period"] < 2.0, (
        f"roi_total_holding_period={row['roi_total_holding_period']} looks like the "
        f"pre-fix gross-cash-multiple bug (expected a net return, e.g. ~1.24 for this property)"
    )


def test_mart04c_scenario_roi_consistent_with_irr_ordering():
    """Across Upside > Base > Downside > Severe Downside, ROI should be
    monotonically ordered the same way IRR is, for a given property --
    catches a source-data mixup (e.g. scenario rows shuffled or a stale
    partial re-copy) even without recomputing the underlying math."""
    df = pd.read_csv(os.path.join(MARTS, "mart_04c_scenarios_extended4.csv"))
    order = ["Severe Downside", "Downside", "Base", "Upside"]
    for pid, g in df.groupby("property_id"):
        g = g.set_index("scenario").reindex(order)
        if g["irr"].isna().any():
            continue
        irr_vals = g["irr"].tolist()
        roi_vals = g["roi_total_holding_period"].tolist()
        assert irr_vals == sorted(irr_vals), f"property {pid}: IRR not monotonic across scenarios"
        assert roi_vals == sorted(roi_vals), f"property {pid}: ROI not monotonic across scenarios"


# --------------------------------------------------------------- mart_03 (Property & Investment)

def test_mart03_no_nan_locality_names():
    """Regression test for the bug this phase's own visual QA found and
    fixed: every property in the mart (including property_id=1, which has
    no Phase 6 financial row) must have a non-null locality_name."""
    df = pd.read_csv(os.path.join(MARTS, "mart_03_property_investment.csv"))
    assert df["locality_name"].notna().all(), (
        f"NaN locality_name found for property_ids: "
        f"{df[df['locality_name'].isna()]['property_id'].tolist()}"
    )


def test_mart03_includes_property_1_insufficient_case():
    df = pd.read_csv(os.path.join(MARTS, "mart_03_property_investment.csv"))
    row = df[df["property_id"] == 1]
    assert len(row) == 1
    assert row.iloc[0]["decision"] == "INSUFFICIENT"


# --------------------------------------------------------------- mart_01 (Portfolio KPIs)

def test_mart01_decision_counts_sum_to_total_evaluated():
    df = pd.read_csv(os.path.join(MARTS, "mart_01_portfolio_kpis.csv")).iloc[0]
    total = (df["decision_invest_count"] + df["decision_hold_count"] +
              df["decision_avoid_count"] + df["decision_insufficient_count"])
    assert total == df["properties_with_full_decision_evaluation"]


def test_mart01_matches_phase9_source_exactly():
    """No drift between the KPI mart and its Phase 9 source -- this mart
    must never recompute or approximate what Phase 9 already decided."""
    kpi = pd.read_csv(os.path.join(MARTS, "mart_01_portfolio_kpis.csv")).iloc[0]
    d9 = pd.read_csv(os.path.join(SOURCES, "phase9", "01_decision_summary.csv"))
    assert int(kpi["decision_invest_count"]) == int((d9["decision"] == "INVEST").sum())
    assert int(kpi["decision_hold_count"]) == int((d9["decision"] == "HOLD").sum())
    assert int(kpi["decision_avoid_count"]) == int((d9["decision"] == "AVOID").sum())
    assert int(kpi["decision_insufficient_count"]) == int((d9["decision"] == "INSUFFICIENT").sum())


# --------------------------------------------------------------- mart_05 (Geo)

def test_mart05_flood_risk_insufficient_not_invented():
    """Per Phase 8 (and re-affirmed at the dashboard layer): flood/
    environmental risk must show INSUFFICIENT DATA, never a fabricated
    score, across every locality."""
    df = pd.read_csv(os.path.join(MARTS, "mart_05_geo.csv"))
    if "flood_risk_status" in df.columns:
        assert (df["flood_risk_status"] == "INSUFFICIENT DATA").all()


# --------------------------------------------------------------- No recomputation

def test_build_marts_contains_no_irr_npv_formulas():
    """Structural check for Section 10.2: the mart builder must not
    recompute financial/risk/geo math -- only reuse Phase 8's already-
    tested market_intelligence helper for the two locality-level fields
    Phase 2 didn't export as CSV."""
    path = os.path.join(_HERE, "..", "marts", "build_marts.py")
    with open(path) as f:
        src = f.read()
    forbidden = ["def npv(", "def irr(", "def compute_metrics(", "def run_monte_carlo("]
    for token in forbidden:
        assert token not in src, f"build_marts.py appears to redefine {token} -- should only reuse existing modules"


# --------------------------------------------------------------- Dashboard HTML freshness

def test_all_seven_dashboards_exist_and_nonempty():
    dash_dir = os.path.join(os.path.dirname(_HERE), "..", "dashboards")
    expected = ["index.html", "dashboard_02_market_locality.html", "dashboard_03_property_investment.html",
                "dashboard_04_financial_risk.html", "dashboard_05_geo.html", "dashboard_06_decision.html",
                "dashboard_07_data_quality.html"]
    for fname in expected:
        path = os.path.join(dash_dir, fname)
        assert os.path.exists(path), f"missing dashboard: {fname}"
        assert os.path.getsize(path) > 1000, f"dashboard {fname} looks empty/truncated"


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_") and callable(obj)]
    passed, failed = 0, []
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed.append(t.__name__)
        except Exception as e:
            print(f"ERROR {t.__name__}: {e}")
            failed.append(t.__name__)
    print(f"\n{passed}/{len(tests)} passed.")
    if failed:
        print("Failed:", failed)
        sys.exit(1)
