"""
Phase 8 -- Batch runner. Unlike Phase 6/7 (8,000 properties, so a demo
sample was used), Phase 8 operates at the LOCALITY level -- only 90 rows
total -- so the full portfolio is run every time, no sampling needed.
"""
import argparse
import os
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from geo_engine import run_geo_engine

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "data", "processed")


def all_locality_ids() -> list:
    loc = pd.read_csv(os.path.join(_DATA_DIR, "localities.csv"))
    return sorted(loc["locality_id"].unique().tolist())


def run_full_batch(source: str = "csv") -> list:
    ids = all_locality_ids()
    return [run_geo_engine(lid, source=source) for lid in ids]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["csv", "db"], default="db")
    args = parser.parse_args()

    batch = run_full_batch(source=args.source)
    passed = sum(1 for b in batch if b["validation_status"] == "PASS")
    limited = sum(1 for b in batch if b["validation_status"] == "PASS WITH LIMITATIONS")
    print(f"Total localities: {len(batch)} | PASS: {passed} | PASS WITH LIMITATIONS: {limited}")
