#!/usr/bin/env python
# coding: utf-8

# In[4]:


"""
Phase 4 -- Data Loader
======================
Single source of truth for loading and joining the Phase 1 (cleaned, `data/processed/`)
tables into model-ready feature frames for Phase 4 predictive models.

Design rules (per Master A-Z Prompt, Section 3.2 / 3.4 / 4.6):
  - No invented values. Every column here traces to a raw processed CSV column.
  - No target leakage: a model's target column, or any column computed FROM the
    target, is never included as a feature for that same model.
  - Deterministic: no randomness in joins/aggregation. Random splits use a fixed
    seed (RANDOM_STATE) for reproducibility.
"""
import os
import pandas as pd
import numpy as np

RANDOM_STATE = 42
DATA_DIR = os.path.abspath("../data")


def _read(name):
    return pd.read_csv(os.path.join(DATA_DIR, f"{name}.csv"))


def load_raw_tables():
    """Load every processed table used downstream. Returns a dict of DataFrames."""
    tables = {}
    for name in [
        "properties", "projects", "localities", "cities", "developers",
        "transactions", "rentals", "listing_history", "market_monthly",
        "economic_monthly", "property_events", "expenses",
    ]:
        tables[name] = _read(name)

    # Parse date columns explicitly (processed CSVs store dates as text).
    tables["projects"]["launch_date"] = pd.to_datetime(tables["projects"]["launch_date"])
    tables["projects"]["completion_date"] = pd.to_datetime(tables["projects"]["completion_date"])
    tables["transactions"]["transaction_date"] = pd.to_datetime(tables["transactions"]["transaction_date"])
    tables["rentals"]["rental_date"] = pd.to_datetime(tables["rentals"]["rental_date"])
    tables["listing_history"]["listing_date"] = pd.to_datetime(tables["listing_history"]["listing_date"])
    tables["market_monthly"]["month"] = pd.to_datetime(tables["market_monthly"]["month"])
    tables["economic_monthly"]["month"] = pd.to_datetime(tables["economic_monthly"]["month"])
    tables["property_events"]["event_date"] = pd.to_datetime(tables["property_events"]["event_date"])
    return tables


def build_property_master():
    """
    property_id-level table: property attributes + project + locality + city +
    developer context. This is the base feature table for Model A (valuation)
    and Model B (rent). asking_price and monthly_rent are BOTH present here as
    raw observed columns -- each model script is responsible for dropping the
    other model's target before training, to avoid circular leakage
    (see docs/limitations.md, "Cross-target leakage").
    """
    t = load_raw_tables()
    props = t["properties"].copy()
    proj = t["projects"][[
        "project_id", "developer_id", "locality_id", "project_type",
        "launch_date", "completion_date", "total_units", "units_sold",
        "units_available", "project_status",
    ]].copy()
    loc = t["localities"][[
        "locality_id", "city_id", "locality_name", "population_density",
        "average_income", "connectivity_score", "safety_score",
        "infrastructure_score", "development_score", "commercial_score",
    ]].copy()
    city = t["cities"][[
        "city_id", "city_name", "population", "average_income", "development_score",
    ]].rename(columns={"average_income": "city_average_income",
                        "development_score": "city_development_score"})
    dev = t["developers"][[
        "developer_id", "rating", "delivery_score", "quality_score",
        "track_record", "market_share",
    ]].rename(columns={"rating": "developer_rating",
                        "delivery_score": "developer_delivery_score",
                        "quality_score": "developer_quality_score",
                        "track_record": "developer_track_record",
                        "market_share": "developer_market_share"})

    df = props.merge(proj, on="project_id", how="left", validate="many_to_one")
    df = df.merge(loc, on="locality_id", how="left", validate="many_to_one")
    df = df.merge(city, on="city_id", how="left", validate="many_to_one")
    df = df.merge(dev, on="developer_id", how="left", validate="many_to_one")

    # Engineered, non-leaky structural features
    df["project_age_years"] = (pd.Timestamp("2026-01-01") - df["launch_date"]).dt.days / 365.25
    df["project_sellthrough_pct"] = np.where(
        df["total_units"] > 0, 100.0 * df["units_sold"] / df["total_units"], np.nan
    )
    df["floor_ratio"] = np.where(df["total_floors"] > 0, df["floor"] / df["total_floors"], np.nan)

    return df


PROPERTY_STRUCTURAL_FEATURES = [
    "property_type", "bedrooms", "bathrooms", "area_sqft", "floor",
    "total_floors", "floor_ratio", "age_years", "parking", "furnishing",
]
LOCALITY_FEATURES = [
    "population_density", "average_income", "connectivity_score",
    "safety_score", "infrastructure_score", "development_score",
    "commercial_score", "city_name", "city_average_income", "city_development_score",
]
PROJECT_DEVELOPER_FEATURES = [
    "project_type", "project_status", "project_age_years", "project_sellthrough_pct",
    "developer_rating", "developer_delivery_score", "developer_quality_score",
    "developer_track_record", "developer_market_share",
]


def build_locality_month_panel():
    """
    locality_id x month panel joined with economic_monthly (national) --
    base table for Model C (price forecasting) and Model D (demand forecasting).
    """
    t = load_raw_tables()
    mm = t["market_monthly"].copy().sort_values(["locality_id", "month"])
    econ = t["economic_monthly"].copy()
    loc = t["localities"][["locality_id", "city_id", "locality_name",
                            "average_income", "connectivity_score", "safety_score",
                            "infrastructure_score", "development_score", "commercial_score"]]

    df = mm.merge(econ, on="month", how="left")
    df = df.merge(loc, on="locality_id", how="left")
    df = df.sort_values(["locality_id", "month"]).reset_index(drop=True)

    # Lag / rolling features computed WITHIN each locality, using only past months
    g = df.groupby("locality_id")
    df["price_sqft_lag1"] = g["average_price_sqft"].shift(1)
    df["price_sqft_lag3"] = g["average_price_sqft"].shift(3)
    df["price_sqft_lag6"] = g["average_price_sqft"].shift(6)
    df["price_sqft_mom_growth"] = g["average_price_sqft"].pct_change(1)
    df["price_sqft_roll3_avg"] = g["average_price_sqft"].transform(lambda s: s.shift(1).rolling(3).mean())
    df["demand_lag1"] = g["demand_index"].shift(1)
    df["demand_lag3"] = g["demand_index"].shift(3)
    df["demand_roll3_avg"] = g["demand_index"].transform(lambda s: s.shift(1).rolling(3).mean())
    df["units_sold_lag1"] = g["units_sold"].shift(1)
    df["absorption_lag1"] = g["absorption_rate"].shift(1)
    df["dom_lag1"] = g["average_days_on_market"].shift(1)

    return df


def build_listing_sale_outcomes():
    """
    listing_history-level table with property + locality context, for
    Model E (days-on-market) and Model F (sale probability).
    Only CLOSED listings (Sold / Expired / Withdrawn) have a known outcome;
    'Active' listings are censored (outcome not yet known) and are excluded
    from training per standard survival-analysis practice, not silently
    imputed (Master Prompt Section 3.2, No Silent Guessing).
    """
    t = load_raw_tables()
    lh = t["listing_history"].copy()
    props = build_property_master()

    # Only keep property attributes known AT LISTING TIME (structural + location),
    # never post-outcome fields (asking_price here is the LISTING's own asking
    # price, which is legitimate -- it is the point-of-listing input, not a
    # future-observed value).
    keep_cols = ["property_id"] + PROPERTY_STRUCTURAL_FEATURES + LOCALITY_FEATURES + PROJECT_DEVELOPER_FEATURES
    df = lh.merge(props[keep_cols], on="property_id", how="left")
    df["listing_month"] = df["listing_date"].dt.to_period("M").dt.to_timestamp()

    closed = df[df["status"].isin(["Sold", "Expired", "Withdrawn"])].copy()
    closed["sold_flag"] = (closed["status"] == "Sold").astype(int)
    return df, closed



# In[ ]:




# In[7]:


# Check if functions run properly
props_df = build_property_master()
print(props_df.head())

# In[8]:


# 1. Test Locality Month Panel
locality_df = build_locality_month_panel()
print("Locality Panel Shape:", locality_df.shape)

# 2. Test Listing Sale Outcomes
all_listings, closed_listings = build_listing_sale_outcomes()
print("All Listings Shape:", all_listings.shape)
print("Closed Listings Shape:", closed_listings.shape)

# In[ ]:



