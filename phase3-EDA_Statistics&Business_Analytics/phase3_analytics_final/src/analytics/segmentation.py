"""
Phase 2, §6 — Group / Segment Analysis
KPIs computed per business segment, directly via SQL GROUP BY against
PostgreSQL (aggregation happens in the database, not in pandas).
"""
import sys
import os
from pathlib import Path

# --- Robust sys.path Resolution (Jupyter Notebook & Script compatible) ---
try:
    current_dir = Path(__file__).resolve().parent
except NameError:
    current_dir = Path(os.getcwd()).resolve()

module_dir = None
for parent in [current_dir] + list(current_dir.parents)[:5]:
    if (parent / "connection.py").exists():
        module_dir = str(parent)
        break
    elif (parent / "db" / "connection.py").exists():
        module_dir = str(parent / "db")
        break

if module_dir and module_dir not in sys.path:
    sys.path.insert(0, module_dir)
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# --- Database Import & Search Path Setup ---
from connection import get_cursor

def _set_search_path(cur):
    """Ensures query resolution across public, core, and analytics schemas."""
    try:
        cur.execute("SET search_path TO public, core, analytics;")
    except Exception:
        pass


def segment_by_city() -> list:
    with get_cursor() as cur:
        _set_search_path(cur)
        cur.execute("""
            SELECT c.city_name,
                   COUNT(DISTINCT p.property_id) AS property_count,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.asking_price) AS median_price,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.asking_price / NULLIF(p.area_sqft,0)) AS median_price_sqft,
                   ROUND(AVG(p.monthly_rent * 12 / NULLIF(p.asking_price,0) * 100)::numeric, 2) AS avg_rental_yield_pct
            FROM properties p
            JOIN projects pj ON pj.project_id = p.project_id
            JOIN localities l ON l.locality_id = pj.locality_id
            JOIN cities c ON c.city_id = l.city_id
            GROUP BY c.city_name
            ORDER BY median_price DESC;
        """)
        return [dict(r) for r in cur.fetchall()]


def segment_by_property_type() -> list:
    with get_cursor() as cur:
        _set_search_path(cur)
        cur.execute("""
            SELECT property_type,
                   COUNT(*) AS property_count,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY asking_price) AS median_price,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY area_sqft) AS median_area,
                   ROUND(AVG(monthly_rent * 12 / NULLIF(asking_price,0) * 100)::numeric, 2) AS avg_rental_yield_pct
            FROM properties
            GROUP BY property_type
            ORDER BY median_price DESC;
        """)
        return [dict(r) for r in cur.fetchall()]


def segment_by_bedroom_count() -> list:
    with get_cursor() as cur:
        _set_search_path(cur)
        cur.execute("""
            SELECT bedrooms,
                   COUNT(*) AS property_count,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY asking_price) AS median_price,
                   ROUND(AVG(asking_price / NULLIF(area_sqft,0))::numeric, 0) AS avg_price_sqft
            FROM properties
            GROUP BY bedrooms
            ORDER BY bedrooms;
        """)
        return [dict(r) for r in cur.fetchall()]


def segment_by_price_band() -> list:
    """Quartile-based price segments — thresholds computed FROM the data."""
    with get_cursor() as cur:
        _set_search_path(cur)
        cur.execute("""
            WITH bounds AS (
                SELECT PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY asking_price) AS p25,
                       PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY asking_price) AS p50,
                       PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY asking_price) AS p75
                FROM properties
            ),
            banded AS (
                SELECT p.*,
                    CASE
                        WHEN p.asking_price <= b.p25 THEN 'Budget (<=P25)'
                        WHEN p.asking_price <= b.p50 THEN 'Mid (P25-P50)'
                        WHEN p.asking_price <= b.p75 THEN 'Upper-Mid (P50-P75)'
                        ELSE 'Premium (>P75)'
                    END AS price_band
                FROM properties p, bounds b
            )
            SELECT price_band, COUNT(*) AS property_count,
                   ROUND(AVG(monthly_rent * 12 / NULLIF(asking_price,0) * 100)::numeric, 2) AS avg_rental_yield_pct,
                   ROUND(AVG(area_sqft)::numeric, 0) AS avg_area_sqft
            FROM banded
            GROUP BY price_band
            ORDER BY MIN(asking_price);
        """)
        return [dict(r) for r in cur.fetchall()]


def segment_by_developer(min_projects: int = 3) -> dict:
    """Top and bottom performing developers by sales velocity."""
    top, bottom = [], []
    with get_cursor() as cur:
        _set_search_path(cur)
        try:
            cur.execute("""
                SELECT developer_name, rating, total_projects, sales_velocity_pct
                FROM v_developer_performance
                WHERE total_projects >= %s AND sales_velocity_pct IS NOT NULL
                ORDER BY sales_velocity_pct DESC LIMIT 5;
            """, (min_projects,))
            top = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT developer_name, rating, total_projects, sales_velocity_pct
                FROM v_developer_performance
                WHERE total_projects >= %s AND sales_velocity_pct IS NOT NULL
                ORDER BY sales_velocity_pct ASC LIMIT 5;
            """, (min_projects,))
            bottom = [dict(r) for r in cur.fetchall()]
        except Exception as e:
            print(f"[Warning] Developer performance query skipped: {e}")

    return {"top_performers": top, "underperformers": bottom}


def segment_by_locality_growth() -> dict:
    """Fast-growing vs high-risk localities."""
    fast_growing, high_dom_risk = [], []
    with get_cursor() as cur:
        _set_search_path(cur)
        try:
            cur.execute("""
                SELECT locality_name, city_name, yoy_growth_pct, demand_supply_ratio, average_days_on_market
                FROM v_locality_ranking ORDER BY yoy_growth_pct DESC LIMIT 5;
            """)
            fast_growing = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT locality_name, city_name, yoy_growth_pct, demand_supply_ratio, average_days_on_market
                FROM v_locality_ranking ORDER BY average_days_on_market DESC LIMIT 5;
            """)
            high_dom_risk = [dict(r) for r in cur.fetchall()]
        except Exception as e:
            print(f"[Warning] Locality ranking query skipped: {e}")

    return {"fastest_growing": fast_growing, "highest_dom_risk": high_dom_risk}


def run_full_segmentation_analysis() -> dict:
    return {
        "by_city": segment_by_city(),
        "by_property_type": segment_by_property_type(),
        "by_bedroom_count": segment_by_bedroom_count(),
        "by_price_band": segment_by_price_band(),
        "by_developer": segment_by_developer(),
        "by_locality_growth": segment_by_locality_growth(),
    }


if __name__ == "__main__":
    result = run_full_segmentation_analysis()

    print("=== By City ===")
    for r in result["by_city"]:
        print(f"  {r['city_name']:12} n={r['property_count']:>5} median_price=₹{float(r['median_price']):>12,.0f} "
              f"yield={r['avg_rental_yield_pct']}%")

    print("\n=== By Price Band ===")
    for r in result["by_price_band"]:
        print(f"  {r['price_band']:22} n={r['property_count']:>5} yield={r['avg_rental_yield_pct']}% avg_area={r['avg_area_sqft']}sqft")

    print("\n=== Top developers by sales velocity ===")
    for r in result["by_developer"]["top_performers"]:
        print(f"  {r['developer_name']:25} rating={r['rating']} velocity={r['sales_velocity_pct']}%")
