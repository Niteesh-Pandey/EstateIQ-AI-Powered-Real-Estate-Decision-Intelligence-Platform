"""
Phase 2, §12 — ML Feature Insights (recommendations only)
Per spec: "Do not automatically change existing ML models in this phase.
Only produce documented recommendations for Phase 3." Nothing in this
file touches src/ml_*.py or ml_artifacts/.
"""
import sys
import os
from pathlib import Path

# --- Robust sys.path Resolution ---
try:
    current_dir = Path(__file__).resolve().parent
except NameError:
    current_dir = Path(os.getcwd()).resolve()

# Locate project directory containing the analytics modules
module_dir = None
for parent in [current_dir] + list(current_dir.parents)[:4]:
    if (parent / "correlations.py").exists():
        module_dir = str(parent)
        break
    elif (parent / "src" / "correlations.py").exists():
        module_dir = str(parent / "src")
        break

if module_dir and module_dir not in sys.path:
    sys.path.insert(0, module_dir)
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# --- Set Database Search Path ---
try:
    from connection import get_cursor
    with get_cursor() as cur:
        cur.execute("SET search_path TO core, analytics, public;")
except Exception:
    pass

# --- Module Imports ---
import correlations
import distributions
import outliers


def generate_ml_feature_recommendations() -> list:
    recs = []

    recs.append({
        "finding": "area_sqft <-> asking_price Pearson r=0.837; area_sqft <-> bedrooms r=0.830",
        "category": "redundant_features / multicollinearity",
        "recommendation": "area_sqft and bedrooms are highly correlated (r=0.83). The existing valuation "
                           "model already uses both — fine for tree-based models (GradientBoostingRegressor, "
                           "robust to multicollinearity) but would be a problem if a future linear/regularized "
                           "model is added. Flag for Phase 3 if a linear baseline model is introduced.",
        "affected_models": ["valuation_v1_gbr (no action needed — tree-based)"],
        "action_required_now": False,
    })

    recs.append({
        "finding": "transaction_price and price_per_sqft show skewness=12.2, excess_kurtosis=172 "
                   "(distributions.py), traced to a data-generation bug (outliers.py)",
        "category": "leakage_candidate / target_quality",
        "recommendation": "Any FUTURE model using raw transaction_price (not asking_price) as a target or "
                           "feature will inherit the runaway-compounding artifact as if it were real signal. "
                           "The existing valuation model correctly uses asking_price (not transaction_price) "
                           "as its target — no change needed there. But if Phase 3+ adds a "
                           "'transaction-price prediction' model, it MUST either (a) wait for the generator "
                           "fix, or (b) log-transform + winsorize price_per_sqft first.",
        "affected_models": ["valuation_v1_gbr (unaffected — uses asking_price)",
                             "any future transaction-price model (would be affected)"],
        "action_required_now": False,
    })

    recs.append({
        "finding": "properties.monthly_rent skewness=0.719 (right-skewed), properties.asking_price "
                   "skewness=1.118 (strongly right-skewed)",
        "category": "transformation_candidate",
        "recommendation": "Both targets are right-skewed, which is normal for price-like variables. "
                           "GradientBoostingRegressor (used in rent_v1_gbr and valuation_v1_gbr) doesn't "
                           "require normality, so this is NOT currently a problem. If a future model "
                           "sensitive to target distribution (e.g. linear regression, neural net with MSE "
                           "loss) is introduced, consider log1p-transforming the target first.",
        "affected_models": ["rent_v1_gbr", "valuation_v1_gbr (both currently fine as tree-based)"],
        "action_required_now": False,
    })

    recs.append({
        "finding": "listing_history.days_on_market outliers (0.42% IQR) show NEEDS_INVESTIGATION "
                   "classification — consistent with the already-known weak DOM model (R²=-0.04)",
        "category": "confirmed_weak_signal",
        "recommendation": "This EDA phase independently confirms (via distribution shape + outlier "
                           "analysis, not just the original model metrics) that days_on_market has no "
                           "recoverable structure in the current dataset. Model Registry's REJECTED status "
                           "for dom_v1_gbr remains correct and does not need re-evaluation. If DOM is fixed "
                           "at the generator level (Phase 3+), re-run distributions.py + hypothesis_tests.py "
                           "on the new data before re-training.",
        "affected_models": ["dom_v1_gbr (confirmed correctly REJECTED)"],
        "action_required_now": False,
    })

    recs.append({
        "finding": "property_type is NOT a significant price driver (Kruskal-Wallis p=0.097, eta²=0.001) "
                   "but IS currently one-hot-encoded as a feature in valuation_v1_gbr",
        "category": "low_value_feature",
        "recommendation": "property_type contributes negligible signal beyond what area_sqft/bedrooms "
                           "already capture (consistent with the model's own feature_importance ranking, "
                           "where property_type dummies rank low). Not harmful to keep (tree-based model "
                           "handles irrelevant features gracefully), but a candidate for removal if "
                           "simplifying the feature set in Phase 3.",
        "affected_models": ["valuation_v1_gbr"],
        "action_required_now": False,
    })

    recs.append({
        "finding": "demand_index <-> units_sold r=0.881, demand_index <-> available_inventory r=-0.762 "
                   "(market-level correlations)",
        "category": "strong_predictive_feature",
        "recommendation": "demand_index is a strong, non-redundant predictor at the market level — already "
                           "used as a feature in price_forecast_v1_gbr_6m and demand_forecast_v1_gbr_6m "
                           "(both READY in the Model Registry, R²=0.78/0.92). This EDA confirms those "
                           "models are using the right signal.",
        "affected_models": ["price_forecast_v1_gbr_6m", "demand_forecast_v1_gbr_6m (both validated, no action)"],
        "action_required_now": False,
    })

    return recs


if __name__ == "__main__":
    recs = generate_ml_feature_recommendations()
    for r in recs:
        print(f"[{r['category']}] {r['finding'][:80]}...")
        print(f"  -> {r['recommendation'][:120]}...")
        print(f"  Affected: {r['affected_models']}")
        print()
