"""
Phase 6, Section 6.2 -- Financial Data Loader
================================================
Sources every OBSERVED financial input from Phase 1's validated tables --
never invents a price, rent, expense, or vacancy figure. Per Master Prompt
Section 13 (Governance), every value this module returns is tagged OBSERVED
because it is a direct measurement from data, not a prediction or assumption.

PRODUCTION PATH (matches Phase 3/5 convention -- live PostgreSQL, no CSV
dependency): `load_property_financials_from_db()` queries `core.*` tables
directly via `db/connection.py`.

DEV/TEST PATH: `load_property_financials_from_csv()` is a test-only
convenience reading the identical rows from `data/processed/*.csv` (the
same files originally loaded into `core.*` -- see Phase 1's loading
pipeline). It exists ONLY so this phase's test suite can be independently
re-checked without a live PostgreSQL instance, WITHOUT changing the
production query path. It is never imported by the report/CSV orchestrators
except via the explicit `--source csv` flag.

What this module does NOT do: it does not decide vacancy rate, expense
ratio, financing terms, holding period, or exit assumptions for a specific
deal -- those are deal-level ASSUMPTIONS a caller must supply explicitly
(Section 6.7 -- Missing Input Policy). This module only answers "what did
this property, and this locality, actually do historically?" so that any
ASSUMED default a caller chooses to use can be justified against real
historical behavior instead of being invented from nothing.
"""
import os
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "data", "processed")

RECURRING_EXPENSE_COLS = ["property_tax", "maintenance", "insurance", "management_cost"]
# renovation_cost is a one-off capital expense, not a recurring operating
# expense -- included separately as a documented one-time cash outflow,
# never folded into NOI's operating expense line (that would silently
# understate NOI in every year that happens to have no renovation).


# ---------------------------------------------------------------- CSV path
def _csv(name: str) -> pd.DataFrame:
    return pd.read_csv(os.path.join(_DATA_DIR, f"{name}.csv"))


def load_property_financials_from_csv(property_id: int) -> dict:
    properties = _csv("properties")
    projects = _csv("projects")
    localities = _csv("localities")
    expenses = _csv("expenses")
    rentals = _csv("rentals")
    transactions = _csv("transactions")
    market_monthly = _csv("market_monthly")
    return _assemble(property_id, properties, projects, localities,
                      expenses, rentals, transactions, market_monthly)


# ----------------------------------------------------------------- DB path
def load_property_financials_from_db(property_id: int) -> dict:
    """PRODUCTION PATH. Queries core.* on the live PostgreSQL database.
    Run with DB_USER / DB_PASSWORD set (see db/connection.py)."""
    sys.path.append(os.path.join(os.path.dirname(_HERE), "..", "db"))
    from connection import get_cursor  # noqa: E402

    with get_cursor() as cur:
        cur.execute("SELECT * FROM core.properties WHERE property_id = %s;", (property_id,))
        prop_rows = cur.fetchall()
        if not prop_rows:
            return {"property_id": property_id, "status": "INSUFFICIENT DATA",
                    "reason": "property_id not found in core.properties"}
        cur.execute("""
            SELECT pr.*, l.locality_id, l.locality_name, l.city_id
            FROM core.properties p
            JOIN core.projects pr ON pr.project_id = p.project_id
            JOIN core.localities l ON l.locality_id = pr.locality_id
            WHERE p.property_id = %s;
        """, (property_id,))
        proj_rows = cur.fetchall()
        cur.execute("SELECT * FROM core.expenses WHERE property_id = %s;", (property_id,))
        exp_rows = cur.fetchall()
        cur.execute("SELECT * FROM core.rentals WHERE property_id = %s;", (property_id,))
        rent_rows = cur.fetchall()
        cur.execute("SELECT * FROM core.transactions WHERE property_id = %s;", (property_id,))
        txn_rows = cur.fetchall()
        locality_id = proj_rows[0]["locality_id"] if proj_rows else None
        mkt_rows = []
        if locality_id is not None:
            cur.execute("""
                SELECT * FROM core.market_monthly WHERE locality_id = %s ORDER BY month;
            """, (locality_id,))
            mkt_rows = cur.fetchall()

    properties = pd.DataFrame(prop_rows)
    projects = pd.DataFrame(proj_rows).rename(columns={"project_id": "project_id"}) if proj_rows else pd.DataFrame()
    localities = pd.DataFrame(proj_rows)[["locality_id", "locality_name", "city_id"]] if proj_rows else pd.DataFrame()
    expenses = pd.DataFrame(exp_rows)
    rentals = pd.DataFrame(rent_rows)
    transactions = pd.DataFrame(txn_rows)
    market_monthly = pd.DataFrame(mkt_rows)
    return _assemble(property_id, properties, projects, localities,
                      expenses, rentals, transactions, market_monthly)


# ------------------------------------------------------------ shared logic
def _assemble(property_id, properties, projects, localities,
              expenses, rentals, transactions, market_monthly) -> dict:
    prop = properties[properties["property_id"] == property_id]
    if prop.empty:
        return {"property_id": property_id, "status": "INSUFFICIENT DATA",
                "reason": "property_id not found in core.properties"}
    prop = prop.iloc[0]

    locality_id, locality_name = None, None
    if "project_id" in prop and not projects.empty and "locality_id" in projects.columns:
        proj = projects[projects["project_id"] == prop["project_id"]]
        if not proj.empty:
            locality_id = int(proj.iloc[0]["locality_id"])
            if not localities.empty:
                loc = localities[localities["locality_id"] == locality_id]
                if not loc.empty:
                    locality_name = loc.iloc[0]["locality_name"]

    result = {
        "property_id": int(property_id),
        "status": "OK",
        "locality_id": locality_id,
        "locality_name": locality_name,
        "property_facts": {
            "asking_price": _num(prop.get("asking_price")),
            "monthly_rent_listed": _num(prop.get("monthly_rent")),
            "area_sqft": _num(prop.get("area_sqft")),
            "property_type": prop.get("property_type"),
            "bedrooms": _num(prop.get("bedrooms")),
            "age_years": _num(prop.get("age_years")),
        },
        "governance": {
            "asking_price": "OBSERVED",
            "monthly_rent_listed": "OBSERVED",
        },
    }

    # --- Recurring operating expenses (OBSERVED, this property's own history)
    p_exp = expenses[expenses["property_id"] == property_id] if not expenses.empty else pd.DataFrame()
    if not p_exp.empty:
        annualized = {}
        for col in RECURRING_EXPENSE_COLS:
            annualized[col] = float(p_exp[col].mean()) if col in p_exp else None
        result["observed_annual_operating_expenses"] = {
            k: (round(v, 2) if v is not None else None) for k, v in annualized.items()
        }
        result["observed_annual_operating_expenses"]["total"] = round(
            sum(v for v in annualized.values() if v is not None), 2
        )
        result["observed_one_time_renovation_cost"] = float(p_exp["renovation_cost"].sum()) \
            if "renovation_cost" in p_exp else None
        result["expense_records_used"] = int(len(p_exp))
    else:
        result["observed_annual_operating_expenses"] = None
        result["expense_records_used"] = 0

    # --- Vacancy (OBSERVED, this property's own rental history)
    p_rent = rentals[rentals["property_id"] == property_id] if not rentals.empty else pd.DataFrame()
    if not p_rent.empty and "vacancy_days" in p_rent and "lease_duration" in p_rent:
        total_vacant = float(p_rent["vacancy_days"].sum())
        total_period = float((p_rent["vacancy_days"] + p_rent["lease_duration"] * 30).sum())
        result["observed_vacancy_rate"] = round(total_vacant / total_period, 4) if total_period > 0 else None
        result["observed_avg_market_rent"] = round(float(p_rent["monthly_rent"].mean()), 2)
        result["rental_records_used"] = int(len(p_rent))
    else:
        result["observed_vacancy_rate"] = None
        result["observed_avg_market_rent"] = None
        result["rental_records_used"] = 0

    # --- Historical transaction price for this exact property (if sold before)
    p_txn = transactions[transactions["property_id"] == property_id] if not transactions.empty else pd.DataFrame()
    result["observed_transaction_history"] = (
        p_txn.sort_values("transaction_date")[["transaction_date", "transaction_price"]]
        .to_dict("records") if not p_txn.empty else []
    )

    # --- Locality-level historical price appreciation (OBSERVED, CAGR from market_monthly)
    result["observed_locality_appreciation"] = _locality_appreciation(market_monthly, locality_id)

    return result


def _locality_appreciation(market_monthly: pd.DataFrame, locality_id) -> dict:
    if market_monthly is None or market_monthly.empty or locality_id is None:
        return {"status": "INSUFFICIENT DATA", "annualized_growth_rate": None}
    m = market_monthly[market_monthly["locality_id"] == locality_id].copy()
    if m.empty or "average_price_sqft" not in m.columns:
        return {"status": "INSUFFICIENT DATA", "annualized_growth_rate": None}
    m["month"] = pd.to_datetime(m["month"])
    m = m.sort_values("month")
    first, last = m.iloc[0], m.iloc[-1]
    n_months = (last["month"].year - first["month"].year) * 12 + (last["month"].month - first["month"].month)
    if n_months <= 0 or first["average_price_sqft"] <= 0:
        return {"status": "INSUFFICIENT DATA", "annualized_growth_rate": None}
    total_growth = last["average_price_sqft"] / first["average_price_sqft"]
    years = n_months / 12.0
    cagr = total_growth ** (1 / years) - 1
    cagr = round(float(cagr), 4)

    # Sanity guard, inherited from Phase 3's documented finding (EDA report,
    # Section "Critical Data Quality Issue"): the synthetic locality-price
    # generator has runaway monthly compounding for a subset of localities,
    # producing CAGRs with no real-world analogue (checked across all 90
    # localities here: median CAGR 12.1%/yr, but 13 localities exceed
    # 30%/yr, up to 132%/yr). REALISTIC_CAGR_CEILING is a documented domain
    # judgement call (a very strong Indian residential market rarely
    # sustains >20%/yr price CAGR over multiple years), not a statistical
    # test -- it exists so this module never silently hands a corrupted
    # growth rate to the financial engine as if it were a trustworthy
    # observed fact (Master Prompt Section 3.2 / 4.6).
    REALISTIC_CAGR_CEILING = 0.20
    reliable = abs(cagr) <= REALISTIC_CAGR_CEILING

    return {
        "status": "OBSERVED" if reliable else "OBSERVED_BUT_UNRELIABLE",
        "first_month": str(first["month"].date()),
        "last_month": str(last["month"].date()),
        "n_months_observed": int(n_months),
        "first_avg_price_sqft": float(first["average_price_sqft"]),
        "last_avg_price_sqft": float(last["average_price_sqft"]),
        "annualized_growth_rate": cagr,
        "reliable_for_use_as_default": reliable,
        "reliability_note": None if reliable else (
            f"CAGR of {cagr:.1%} exceeds the {REALISTIC_CAGR_CEILING:.0%}/yr domain "
            "sanity ceiling and is consistent with the Phase 3 EDA report's documented "
            "locality-price-generator compounding bug. This value must NOT be used as "
            "a default appreciation assumption; the financial engine requires an "
            "explicit, caller-supplied appreciation_rate for this locality instead."
        ),
    }


def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return float(v)


if __name__ == "__main__":
    import json
    print(json.dumps(load_property_financials_from_csv(1), indent=2, default=str))
