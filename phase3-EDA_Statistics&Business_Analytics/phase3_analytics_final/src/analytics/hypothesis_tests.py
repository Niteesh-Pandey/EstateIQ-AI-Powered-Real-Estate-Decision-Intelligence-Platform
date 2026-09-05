"""
Phase 2, §9/§10 — Hypothesis Testing + Effect Size
Every test: states H0/H1, checks assumptions (normality via Shapiro on a
sample, since n is often >5000 which invalidates Shapiro directly — uses
skewness/kurtosis heuristic + notes the tradeoff), reports statistic,
p-value, effect size, and a plain-language business interpretation.
Alpha = 0.05 throughout.
"""
import sys, os

# Notebook-safe path insertion
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..", "db")))

import numpy as np
from scipy import stats
from connection import get_cursor

ALPHA = 0.05


def _fetch_groups(query: str, params: tuple = None) -> dict:
    with get_cursor() as cur:
        # Ensures PostgreSQL checks core and public schemas
        cur.execute("SET search_path TO core, public;")
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        rows = cur.fetchall()

    groups = {}
    for r in rows:
        key = r["group_col"] if isinstance(r, dict) and "group_col" in r else r[0]
        val = r["val_col"] if isinstance(r, dict) and "val_col" in r else r[1]

        if val is not None:
            groups.setdefault(key, []).append(float(val))

    return {k: np.array(v) for k, v in groups.items()}


def _check_normality_heuristic(values: np.ndarray) -> dict:
    """For n>5000, Shapiro-Wilk becomes over-sensitive to trivial deviations.
    Use skewness/kurtosis as a practical heuristic instead, documented here."""
    if len(values) == 0:
        return {"skewness": 0.0, "excess_kurtosis": 0.0, "roughly_normal": False}
    skew = float(stats.skew(values))
    kurt = float(stats.kurtosis(values))
    roughly_normal = abs(skew) < 1 and abs(kurt) < 2
    return {"skewness": round(skew, 3), "excess_kurtosis": round(kurt, 3), "roughly_normal": roughly_normal}


def cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    n1, n2 = len(group1), len(group2)
    if n1 <= 1 or n2 <= 1:
        return 0.0
    pooled_std = np.sqrt(((n1 - 1) * np.var(group1, ddof=1) + (n2 - 1) * np.var(group2, ddof=1)) / (n1 + n2 - 2))
    if pooled_std == 0:
        return 0.0
    return (np.mean(group1) - np.mean(group2)) / pooled_std


def _effect_size_label_d(d: float) -> str:
    d = abs(d)
    if d < 0.2:
        return "negligible"
    if d < 0.5:
        return "small"
    if d < 0.8:
        return "medium"
    return "large"


def eta_squared_from_anova(groups: list) -> float:
    if not groups:
        return 0.0
    all_vals = np.concatenate(groups)
    grand_mean = np.mean(all_vals)
    ss_between = sum(len(g) * (np.mean(g) - grand_mean) ** 2 for g in groups)
    ss_total = sum((all_vals - grand_mean) ** 2)
    return float(ss_between / ss_total) if ss_total else 0.0


def _eta_squared_label(eta: float) -> str:
    if eta < 0.01:
        return "negligible"
    if eta < 0.06:
        return "small"
    if eta < 0.14:
        return "medium"
    return "large"


# ---------------- TEST A: does median price differ between two cities? ----------------
def test_price_between_two_cities(city_a: str, city_b: str) -> dict:
    query = """
        SELECT c.city_name AS group_col, p.asking_price AS val_col
        FROM properties p
        JOIN projects pj ON pj.project_id = p.project_id
        JOIN localities l ON l.locality_id = pj.locality_id
        JOIN cities c ON c.city_id = l.city_id
        WHERE c.city_name IN (%s, %s);
    """
    groups = _fetch_groups(query, (city_a, city_b))

    g1 = groups.get(city_a, np.array([]))
    g2 = groups.get(city_b, np.array([]))

    if len(g1) == 0 or len(g2) == 0:
        return {"error": f"Insufficient data for cities {city_a} and/or {city_b}"}

    norm1, norm2 = _check_normality_heuristic(g1), _check_normality_heuristic(g2)
    use_normal_test = norm1["roughly_normal"] and norm2["roughly_normal"]

    if use_normal_test:
        stat, p = stats.ttest_ind(g1, g2, equal_var=False)  # Welch's t-test (unequal variance safe default)
        test_name = "Welch's t-test"
    else:
        stat, p = stats.mannwhitneyu(g1, g2, alternative="two-sided")
        test_name = "Mann-Whitney U"

    d = cohens_d(g1, g2)
    return {
        "test": test_name,
        "H0": f"Median asking_price is equal between {city_a} and {city_b}",
        "H1": f"Median asking_price differs between {city_a} and {city_b}",
        "alpha": ALPHA,
        "statistic": round(float(stat), 3),
        "p_value": round(float(p), 5),
        "significant": bool(p < ALPHA),
        "group_a": {"city": city_a, "n": len(g1), "median": round(float(np.median(g1)), 0), "normality": norm1},
        "group_b": {"city": city_b, "n": len(g2), "median": round(float(np.median(g2)), 0), "normality": norm2},
        "effect_size": {"cohens_d": round(float(d), 3), "label": _effect_size_label_d(d)},
        "business_interpretation": (
            f"{'Statistically significant' if p < ALPHA else 'Not statistically significant'} price "
            f"difference between {city_a} and {city_b} (p={p:.4f}). Effect size is "
            f"{_effect_size_label_d(d)} (Cohen's d={d:.2f})."
        ),
    }


# ---------------- TEST B: does price differ across property types? (ANOVA/Kruskal-Wallis) ----------------
def test_price_across_property_types() -> dict:
    groups_dict = _fetch_groups("SELECT property_type AS group_col, asking_price AS val_col FROM properties;")
    groups = list(groups_dict.values())

    if not groups:
        return {"error": "No property type data available"}

    normality = {k: _check_normality_heuristic(v) for k, v in groups_dict.items()}
    all_normal = all(n["roughly_normal"] for n in normality.values())

    if all_normal:
        stat, p = stats.f_oneway(*groups)
        test_name = "One-way ANOVA"
    else:
        stat, p = stats.kruskal(*groups)
        test_name = "Kruskal-Wallis H"

    eta = eta_squared_from_anova(groups)
    return {
        "test": test_name,
        "H0": "Median asking_price is equal across all property types",
        "H1": "At least one property type has a different median asking_price",
        "alpha": ALPHA,
        "statistic": round(float(stat), 3),
        "p_value": round(float(p), 8),
        "significant": bool(p < ALPHA),
        "group_medians": {k: round(float(np.median(v)), 0) for k, v in groups_dict.items()},
        "group_sizes": {k: len(v) for k, v in groups_dict.items()},
        "effect_size": {"eta_squared": round(float(eta), 4), "label": _eta_squared_label(eta)},
        "business_interpretation": (
            f"Property type {'is' if p < ALPHA else 'is not'} significantly associated with price "
            f"(p={p:.2e}). Effect size eta²={eta:.3f} ({_eta_squared_label(eta)})."
        ),
    }


# ---------------- TEST C: rental yield between property types (categorical -> numeric) ----------------
def test_rental_yield_across_property_types() -> dict:
    query = """
        SELECT property_type AS group_col, (monthly_rent * 12 / NULLIF(asking_price,0)) * 100 AS val_col
        FROM properties WHERE monthly_rent IS NOT NULL;
    """
    groups_dict = _fetch_groups(query)
    groups = list(groups_dict.values())

    if not groups:
        return {"error": "No rental yield data available"}

    stat, p = stats.kruskal(*groups)  # yield is a tight normal by construction, but Kruskal is robust regardless
    eta = eta_squared_from_anova(groups)
    return {
        "test": "Kruskal-Wallis H",
        "H0": "Median rental yield is equal across property types",
        "H1": "At least one property type has different median rental yield",
        "alpha": ALPHA,
        "statistic": round(float(stat), 3),
        "p_value": round(float(p), 5),
        "significant": bool(p < ALPHA),
        "group_medians": {k: round(float(np.median(v)), 2) for k, v in groups_dict.items()},
        "effect_size": {"eta_squared": round(float(eta), 4), "label": _eta_squared_label(eta)},
        "business_interpretation": (
            f"Rental yield {'differs' if p < ALPHA else 'does not differ'} significantly by property type "
            f"(p={p:.4f}), effect size is {_eta_squared_label(eta)} (eta²={eta:.4f})."
        ),
    }


# ---------------- TEST D: buyer_type association with transaction_type (Chi-square) ----------------
def test_buyer_type_vs_transaction_type() -> dict:
    with get_cursor() as cur:
        cur.execute("SET search_path TO core, public;")
        cur.execute("SELECT buyer_type, transaction_type FROM transactions;")
        rows = cur.fetchall()

    if not rows:
        return {"error": "No transaction data available"}

    get_b = lambda r: r["buyer_type"] if isinstance(r, dict) and "buyer_type" in r else r[0]
    get_t = lambda r: r["transaction_type"] if isinstance(r, dict) and "transaction_type" in r else r[1]

    buyer_types = sorted(set(get_b(r) for r in rows if get_b(r) is not None))
    tx_types = sorted(set(get_t(r) for r in rows if get_t(r) is not None))

    table = np.zeros((len(buyer_types), len(tx_types)))
    for r in rows:
        b_val, t_val = get_b(r), get_t(r)
        if b_val in buyer_types and t_val in tx_types:
            i, j = buyer_types.index(b_val), tx_types.index(t_val)
            table[i, j] += 1

    chi2, p, dof, expected = stats.chi2_contingency(table)
    n = table.sum()
    cramers_v = np.sqrt(chi2 / (n * (min(table.shape) - 1))) if min(table.shape) > 1 and n > 0 else 0.0

    return {
        "test": "Chi-square test of independence",
        "H0": "buyer_type and transaction_type are independent",
        "H1": "buyer_type and transaction_type are associated",
        "alpha": ALPHA,
        "statistic": round(float(chi2), 3),
        "p_value": round(float(p), 5),
        "dof": int(dof),
        "significant": bool(p < ALPHA),
        "contingency_table": {
            buyer_types[i]: {tx_types[j]: int(table[i, j]) for j in range(len(tx_types))}
            for i in range(len(buyer_types))
        },
        "effect_size": {
            "cramers_v": round(float(cramers_v), 4),
            "label": "negligible" if cramers_v < 0.1 else "small" if cramers_v < 0.3 else "medium/large"
        },
        "business_interpretation": (
            f"{'Significant' if p < ALPHA else 'No significant'} association between buyer type and "
            f"transaction type (p={p:.4f}, Cramér's V={cramers_v:.3f})."
        ),
    }


def run_full_hypothesis_testing() -> dict:
    return {
        "test_a_price_mumbai_vs_chennai": test_price_between_two_cities("Mumbai", "Chennai"),
        "test_b_price_by_property_type": test_price_across_property_types(),
        "test_c_yield_by_property_type": test_rental_yield_across_property_types(),
        "test_d_buyer_type_vs_transaction_type": test_buyer_type_vs_transaction_type(),
    }


if __name__ == "__main__":
    results = run_full_hypothesis_testing()
    for name, r in results.items():
        print(f"=== {name} ===")
        print(f"  {r.get('test')}: statistic={r.get('statistic')}, p={r.get('p_value')}, significant={r.get('significant')}")
        print(f"  {r.get('business_interpretation')}\n")
