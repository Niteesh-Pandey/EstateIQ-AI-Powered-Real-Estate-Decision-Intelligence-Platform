import argparse
import os
import sys
import pandas as pd

# Set up paths and imports
_HERE = os.getcwd()
sys.path.insert(0, _HERE)
from geo_engine import run_geo_engine

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "data", "processed")

# Set DB credentials
os.environ["DB_USER"] = "postgres"  # Adjust if your username differs
os.environ["DB_PASSWORD"] = "admin123"
os.environ["DB_NAME"] = "real_estate_db"

def all_locality_ids() -> list:
    loc = pd.read_csv(os.path.join(_DATA_DIR, "localities.csv"))
    return sorted(loc["locality_id"].unique().tolist())

def run_full_batch(source: str = "csv") -> list:
    ids = all_locality_ids()
    return [run_geo_engine(lid, source=source) for lid in ids]

# Execute batch run
batch = run_full_batch(source="db")
passed = sum(1 for b in batch if b["validation_status"] == "PASS")
limited = sum(1 for b in batch if b["validation_status"] == "PASS WITH LIMITATIONS")
print(f"Total localities: {len(batch)} | PASS: {passed} | PASS WITH LIMITATIONS: {limited}")