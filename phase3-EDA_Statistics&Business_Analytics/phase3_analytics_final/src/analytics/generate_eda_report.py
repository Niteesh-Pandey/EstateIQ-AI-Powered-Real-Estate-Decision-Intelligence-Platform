"""
Phase 2, §13 — Analytical Report Generator
Runs every analytics module fresh against LIVE PostgreSQL and compiles a
single reproducible Markdown report.

Run: export DB_USER=... DB_PASSWORD=...
     python3 src/analytics/generate_eda_report.py
"""
import sys, os, json
from datetime import datetime

current_dir = os.getcwd()
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "..", "..", "db"))
OUT_PATH = os.path.join(current_dir, "..", "..", "docs", "eda_report.md")

from connection import health_check
import data_dictionary, data_quality, descriptive_stats, distributions
import correlations, segmentation, time_series, outliers, hypothesis_tests
import insights as insights_mod, ml_feature_insights


def fmt(v, spec=",.1f"):
    try:
        if v is None:
            return "n/a"
        return format(float(v), spec)
    except (TypeError, ValueError):
        return str(v)


def safe_run(func, default, label):
    """Runs an analytics function defensively — a failure in one section
    should not take down the whole report."""
    try:
        return func()
    except Exception as e:
        print(f"[Warning] {label} skipped: {e}")
        return default


def build_report() -> str:
    lines = []

    # 0. Connection & Health check
    health = safe_run(health_check, {"database": "real_estate_db", "properties_row_count": 0, "postgres_version": ""}, "health_check")

    lines.append("# Real Estate Platform — EDA & Statistical Analytics Report\n")
    lines.append(f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} against live PostgreSQL "
                  f"({health.get('database')}, {str(health.get('postgres_version', ''))[:30]}). "
                  f"Reproducible via `python3 src/analytics/generate_eda_report.py`.*\n")

    # 1. Business objective
    lines.append("## 1. Business Objective\n")
    lines.append("Understand the statistical structure of the real estate dataset — price drivers, "
                  "market segmentation, time trends, and data-quality issues — to (a) validate existing "
                  "ML model design choices and (b) surface findings that inform Phase 3+ model/decision "
                  "engine work. This is descriptive/inferential analytics, not a new ML model.\n")

    # 2. Dataset overview
    lines.append("## 2. Dataset Overview\n")
    lines.append(f"- **Database**: `{health.get('database')}` (PostgreSQL, live)")
    lines.append(f"- **properties row count** (live check): {health.get('properties_row_count')}")
    ddict = safe_run(data_dictionary.build_data_dictionary, [], "data_dictionary")
    n_tables = len(set(r["table_name"] for r in ddict)) if ddict else 0
    lines.append(f"- **Data dictionary**: {len(ddict)} columns across {n_tables} tables — see `src/analytics/data_dictionary.py`\n")

    # 3. Data quality
    lines.append("## 3. Data Quality\n")
    dq = safe_run(data_quality.run_full_data_quality_report,
                  {"referential_integrity": [], "numeric_profiles": []}, "data_quality")
    lines.append("**Referential integrity** (all FK checks against live PostgreSQL):\n")
    for r in dq.get("referential_integrity", []):
        lines.append(f"- `{r['child']}.{r['fk']}` → `{r['parent']}`: **{r['orphan_count']} orphans**")
    lines.append("\n**Key numeric field null rates:**\n")
    lines.append("| Table.Column | N | Null % | Mean | Median | Std |")
    lines.append("|---|---|---|---|---|---|")
    for r in dq.get("numeric_profiles", [])[:6]:
        lines.append(f"| {r['table']}.{r['column']} | {r['row_count']} | {r['null_pct']}% | "
                      f"{fmt(r['mean_val'])} | {fmt(r['median'])} | {fmt(r['std_val'])} |")
    lines.append("")

    # 4. Descriptive statistics
    lines.append("## 4. Descriptive Statistics\n")
    desc = safe_run(descriptive_stats.build_descriptive_stats_table, [], "descriptive_stats")
    lines.append("| Metric | N | Mean | Median | Std | P95 | CV |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in desc:
        cv = r.get("coefficient_of_variation")
        cv_str = f"{cv:.2f}" if isinstance(cv, (int, float)) else "n/a"
        lines.append(f"| {r['label']} | {r['row_count']} | {fmt(r['mean_val'])} | {fmt(r['median'])} | "
                      f"{fmt(r['std_val'])} | {fmt(r.get('p95'))} | {cv_str} |")
    lines.append("")

    # 5. Distributions
    lines.append("## 5. Distribution Analysis\n")
    dist = safe_run(distributions.run_full_distribution_analysis, [], "distributions")
    lines.append("| Metric | Skewness | Shape | Excess Kurtosis | Tail Behavior |")
    lines.append("|---|---|---|---|---|")
    for r in dist:
        lines.append(f"| {r['label']} | {r['skewness']} | {r['shape']} | {r['excess_kurtosis']} | {r['tail_behavior']} |")
    lines.append("\nCharts saved to `docs/eda_charts/`: " + ", ".join(os.path.basename(r["chart_path"]) for r in dist if "chart_path" in r) + "\n")

    # 6. Correlations
    lines.append("## 6. Correlation Analysis\n")
    lines.append("*Correlation does not imply causation — all relationships below are observed associations only.*\n")
    corr = safe_run(correlations.run_full_correlation_analysis,
                     {"property_level": {"top_pearson": [], "heatmap": ""}, "market_level": {"top_pearson": [], "heatmap": ""}},
                     "correlations")
    lines.append("**Strongest property-level correlations (Pearson):**\n")
    for c in corr.get("property_level", {}).get("top_pearson", [])[:5]:
        lines.append(f"- `{c['var1']}` ↔ `{c['var2']}`: r = {c['correlation']}")
    lines.append("\n**Strongest market-level correlations (Pearson):**\n")
    for c in corr.get("market_level", {}).get("top_pearson", [])[:5]:
        lines.append(f"- `{c['var1']}` ↔ `{c['var2']}`: r = {c['correlation']}")
    lines.append(f"\nHeatmaps: `{os.path.basename(corr.get('property_level', {}).get('heatmap', ''))}`, "
                  f"`{os.path.basename(corr.get('market_level', {}).get('heatmap', ''))}`\n")

    # 7. Segmentation
    lines.append("## 7. Segment Analysis\n")
    seg = safe_run(segmentation.run_full_segmentation_analysis,
                    {"by_city": [], "by_developer": {"top_performers": []}}, "segmentation")
    lines.append("**By city (median price):**\n")
    lines.append("| City | N | Median Price | Median ₹/sqft | Rental Yield |")
    lines.append("|---|---|---|---|---|")
    for r in seg.get("by_city", []):
        lines.append(f"| {r.get('city_name')} | {r.get('property_count')} | ₹{fmt(r.get('median_price'), ',.0f')} | "
                      f"₹{fmt(r.get('median_price_sqft'), ',.0f')} | {r.get('avg_rental_yield_pct')}% |")
    lines.append("\n**Top 3 developers by sales velocity:**\n")
    for r in seg.get("by_developer", {}).get("top_performers", [])[:3]:
        lines.append(f"- {r.get('developer_name')}: {r.get('sales_velocity_pct')}% velocity, rating {r.get('rating')}")
    lines.append("")

    # 8. Time series
    lines.append("## 8. Time-Series Analysis\n")
    ts = safe_run(time_series.run_full_time_series_analysis,
                  {"n_months_observed": 0, "date_range": "N/A", "price_summary": {}, "demand_summary": {},
                   "price_quarterly_yearly": {"yearly": {}}}, "time_series")
    lines.append(f"- Observed **{ts.get('n_months_observed')} months**: {ts.get('date_range')}")
    lines.append(f"- Latest price snapshot: {json.dumps(ts.get('price_summary'))}")
    lines.append(f"- Latest demand snapshot: {json.dumps(ts.get('demand_summary'))}")
    lines.append(f"- Yearly avg price/sqft: {json.dumps(ts.get('price_quarterly_yearly', {}).get('yearly'))}")
    lines.append(f"\n⚠️ **See §9 Outlier Analysis** — price growth figures are affected by data generation compounding.\n")

    # 9. Outliers
    lines.append("## 9. Outlier Analysis\n")
    out = safe_run(outliers.run_full_outlier_analysis, [], "outliers")
    for r in out:
        lines.append(f"### {r.get('metric')} — `{r.get('classification')}`")
        lines.append(f"- IQR outliers: {r.get('iqr', {}).get('outlier_count')} ({r.get('iqr', {}).get('outlier_pct')}%)")
        lines.append(f"- Z-score outliers: {r.get('zscore', {}).get('outlier_count')} ({r.get('zscore', {}).get('outlier_pct')}%)")
        lines.append(f"- **Evidence**: {r.get('evidence')}")
        lines.append(f"- **Recommended action**: {r.get('recommended_action')}\n")

    # 10. Hypothesis testing
    lines.append("## 10. Hypothesis Testing & Effect Sizes\n")
    lines.append("*Alpha = 0.05 throughout.*\n")
    hyp = safe_run(hypothesis_tests.run_full_hypothesis_testing, {}, "hypothesis_tests")
    for name, r in hyp.items():
        lines.append(f"### {name}")
        lines.append(f"- **Test**: {r.get('test')} | H0: {r.get('H0')}")
        lines.append(f"- **Statistic**: {r.get('statistic')}, **p-value**: {r.get('p_value')}, "
                      f"**significant**: {r.get('significant')}")
        lines.append(f"- **Effect size**: {r.get('effect_size')}")
        lines.append(f"- **Interpretation**: {r.get('business_interpretation')}\n")

    # 11. Business insights
    lines.append("## 11. Key Business Insights\n")
    insights = safe_run(insights_mod.generate_insights, [], "insights")
    for i, ins in enumerate(insights, 1):
        lines.append(f"**Insight {i} ({ins.get('insight_type')}, confidence: {ins.get('confidence')})**")
        lines.append(f"- {ins.get('observation')}")
        lines.append(f"- *Implication*: {ins.get('business_implication')}")
        lines.append(f"- *Action*: {ins.get('recommended_action')}\n")

    # 12. ML implications
    lines.append("## 12. ML Feature Insights\n")
    ml_recs = safe_run(ml_feature_insights.generate_ml_feature_recommendations, [], "ml_feature_insights")
    for r in ml_recs:
        lines.append(f"- **[{r.get('category')}]** {r.get('finding')}")
        lines.append(f"  - {r.get('recommendation')}\n")

    # 13. Limitations
    lines.append("## 13. Limitations\n")
    lines.append("- This report analyzes a **synthetic dataset** — findings describe generator behavior, "
                  "not real real-estate markets.")
    lines.append("- The transaction-price runaway-compounding bug (§9) means all price-growth figures in "
                  "§8 should be treated as a generator artifact, not a market signal, until fixed at source.")
    lines.append("- Hypothesis tests use a skewness/kurtosis heuristic for normality (not Shapiro-Wilk) "
                  "because sample sizes (n>5000) make Shapiro over-sensitive to trivial deviations.")
    lines.append("- No source data or existing ML models were modified in this phase (Phase 2 = analytics only).")

    return "\n".join(lines)


if __name__ == "__main__":
    report = build_report()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report written to {OUT_PATH} ({len(report)} chars, {report.count(chr(10))} lines)")
