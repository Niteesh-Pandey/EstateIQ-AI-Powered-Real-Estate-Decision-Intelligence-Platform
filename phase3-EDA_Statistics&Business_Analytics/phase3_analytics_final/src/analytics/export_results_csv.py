"""
Phase 3 -- Export analysis results as CSV files.
Runs every analytics module fresh against the live PostgreSQL database
(exactly like generate_eda_report.py) and writes each module's output
as a separate CSV file under docs/eda_results_csv/, alongside the
existing Markdown report and chart PNGs.
"""
import sys, os, json
import pandas as pd

current_dir = os.getcwd()
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "..", "..", "db"))
OUT_DIR = os.path.join(current_dir, "..", "..", "docs", "eda_results_csv")
os.makedirs(OUT_DIR, exist_ok=True)

import data_dictionary, data_quality, descriptive_stats, distributions
import correlations, segmentation, time_series, outliers, hypothesis_tests
import insights as insights_mod, ml_feature_insights


def save(df, name):
    path = os.path.join(OUT_DIR, name)
    df.to_csv(path, index=False)
    print(f"  wrote {name} ({len(df)} rows)")


def safe(func, label):
    try:
        return func()
    except Exception as e:
        print(f"[Warning] {label} skipped: {e}")
        return None


def main():
    print("Exporting analysis results to CSV...")

    # 1. Data dictionary
    ddict = safe(data_dictionary.build_data_dictionary, "data_dictionary")
    if ddict:
        save(pd.DataFrame(ddict), "01_data_dictionary.csv")

    # 2. Data quality
    dq = safe(data_quality.run_full_data_quality_report, "data_quality")
    if dq:
        if dq.get("numeric_profiles"):
            df = pd.DataFrame(dq["numeric_profiles"]).drop(columns=["top_categories"], errors="ignore")
            save(df, "02_data_quality_numeric_profiles.csv")
        if dq.get("categorical_profiles"):
            flat = [{k: v for k, v in r.items() if k not in ("top_categories", "rare_categories")}
                    for r in dq["categorical_profiles"]]
            save(pd.DataFrame(flat), "02_data_quality_categorical_profiles.csv")
        if dq.get("date_profiles"):
            save(pd.DataFrame(dq["date_profiles"]), "02_data_quality_date_profiles.csv")
        if dq.get("referential_integrity"):
            save(pd.DataFrame(dq["referential_integrity"]), "02_data_quality_referential_integrity.csv")

    # 3. Descriptive statistics
    desc = safe(descriptive_stats.build_descriptive_stats_table, "descriptive_stats")
    if desc:
        save(pd.DataFrame(desc), "03_descriptive_statistics.csv")

    # 4. Distributions
    dist = safe(distributions.run_full_distribution_analysis, "distributions")
    if dist:
        save(pd.DataFrame(dist), "04_distribution_analysis.csv")

    # 5. Correlations
    corr = safe(correlations.run_full_correlation_analysis, "correlations")
    if corr:
        save(pd.DataFrame(corr["property_level"]["top_pearson"]), "05_correlations_property_level_pearson.csv")
        save(pd.DataFrame(corr["property_level"]["top_spearman"]), "05_correlations_property_level_spearman.csv")
        save(pd.DataFrame(corr["market_level"]["top_pearson"]), "05_correlations_market_level_pearson.csv")
        save(pd.DataFrame(corr["market_level"]["top_spearman"]), "05_correlations_market_level_spearman.csv")
        checks = [corr["area_vs_price_check"], corr["demand_vs_dom_check"], corr["interest_rate_vs_demand_check"]]
        save(pd.DataFrame(checks), "05_correlations_pearson_vs_spearman_checks.csv")

    # 6. Segmentation
    seg = safe(segmentation.run_full_segmentation_analysis, "segmentation")
    if seg:
        if seg.get("by_city"):
            save(pd.DataFrame(seg["by_city"]), "06_segment_by_city.csv")
        if seg.get("by_property_type"):
            save(pd.DataFrame(seg["by_property_type"]), "06_segment_by_property_type.csv")
        if seg.get("by_bedroom_count"):
            save(pd.DataFrame(seg["by_bedroom_count"]), "06_segment_by_bedroom_count.csv")
        if seg.get("by_price_band"):
            save(pd.DataFrame(seg["by_price_band"]), "06_segment_by_price_band.csv")
        top = seg.get("by_developer", {}).get("top_performers")
        bottom = seg.get("by_developer", {}).get("underperformers")
        if top:
            save(pd.DataFrame(top), "06_segment_developer_top_performers.csv")
        if bottom:
            save(pd.DataFrame(bottom), "06_segment_developer_underperformers.csv")
        fast = seg.get("by_locality_growth", {}).get("fastest_growing")
        risky = seg.get("by_locality_growth", {}).get("highest_dom_risk")
        if fast:
            save(pd.DataFrame(fast), "06_segment_locality_fastest_growing.csv")
        if risky:
            save(pd.DataFrame(risky), "06_segment_locality_highest_dom_risk.csv")

    # 7. Time series
    ts = safe(time_series.run_full_time_series_analysis, "time_series")
    if ts:
        summary_rows = [
            {"section": "n_months_observed", "value": ts.get("n_months_observed")},
            {"section": "date_range", "value": ts.get("date_range")},
            {"section": "price_summary", "value": json.dumps(ts.get("price_summary"))},
            {"section": "demand_summary", "value": json.dumps(ts.get("demand_summary"))},
            {"section": "yearly_avg_price_sqft", "value": json.dumps(ts.get("price_quarterly_yearly", {}).get("yearly"))},
        ]
        save(pd.DataFrame(summary_rows), "07_time_series_summary.csv")
        quarterly = ts.get("price_quarterly_yearly", {}).get("quarterly")
        if quarterly:
            save(pd.DataFrame(list(quarterly.items()), columns=["quarter", "avg_price_sqft"]),
                 "07_time_series_quarterly_price.csv")

    trend_df = safe(time_series.fetch_national_market_trend, "time_series_national_trend")
    if trend_df is not None:
        save(trend_df, "07_time_series_national_monthly_trend.csv")

    # 8. Outliers
    out = safe(outliers.run_full_outlier_analysis, "outliers")
    if out:
        rows = []
        for r in out:
            rows.append({
                "metric": r.get("metric"), "classification": r.get("classification"),
                "iqr_outlier_count": r.get("iqr", {}).get("outlier_count"),
                "iqr_outlier_pct": r.get("iqr", {}).get("outlier_pct"),
                "zscore_outlier_count": r.get("zscore", {}).get("outlier_count"),
                "zscore_outlier_pct": r.get("zscore", {}).get("outlier_pct"),
                "evidence": r.get("evidence"), "recommended_action": r.get("recommended_action"),
            })
        save(pd.DataFrame(rows), "08_outlier_analysis.csv")

    # 9. Hypothesis tests
    hyp = safe(hypothesis_tests.run_full_hypothesis_testing, "hypothesis_tests")
    if hyp:
        rows = []
        for name, r in hyp.items():
            rows.append({
                "test_name": name, "test": r.get("test"), "H0": r.get("H0"),
                "statistic": r.get("statistic"), "p_value": r.get("p_value"),
                "significant": r.get("significant"), "effect_size": json.dumps(r.get("effect_size")),
                "business_interpretation": r.get("business_interpretation"),
            })
        save(pd.DataFrame(rows), "09_hypothesis_tests.csv")

    # 10. Business insights
    insights = safe(insights_mod.generate_insights, "insights")
    if insights:
        save(pd.DataFrame(insights), "10_business_insights.csv")

    # 11. ML feature insights
    ml_recs = safe(ml_feature_insights.generate_ml_feature_recommendations, "ml_feature_insights")
    if ml_recs:
        save(pd.DataFrame(ml_recs), "11_ml_feature_insights.csv")

    print(f"\nAll CSV results written to {os.path.abspath(OUT_DIR)}")


if __name__ == "__main__":
    main()
