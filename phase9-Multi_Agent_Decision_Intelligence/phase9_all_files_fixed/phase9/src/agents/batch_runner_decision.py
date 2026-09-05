import sys
import os
import pandas as pd
import warnings

# Create dummy class mapping for pickle unpickling compatibility
try:
    import sklearn._loss.loss as loss_module
    if not hasattr(loss_module, 'CyHalfSquaredError'):
        loss_module.CyHalfSquaredError = getattr(loss_module, 'HalfSquaredError', None)
    sys.modules['_loss'] = loss_module
except (ImportError, AttributeError):
    pass

from sklearn.exceptions import InconsistentVersionWarning
warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

# Set database environment variables
os.environ["DB_USER"] = "postgres"
os.environ["DB_PASSWORD"] = "admin123"
os.environ["DB_NAME"] = "real_estate_db"

# Dynamic Folder Paths Setup
_HERE = os.path.abspath('') 

if os.path.basename(_HERE) == "agents":
    AGENTS_DIR = _HERE
    SRC_DIR = os.path.dirname(_HERE)
else:
    SRC_DIR = os.path.join(_HERE, "src") if os.path.exists(os.path.join(_HERE, "src")) else _HERE
    AGENTS_DIR = os.path.join(SRC_DIR, "agents")

GEO_DIR = os.path.join(SRC_DIR, "geo")
FINANCE_DIR = os.path.join(SRC_DIR, "finance")

# Setup sys.path priority
paths_to_add = [AGENTS_DIR, SRC_DIR, GEO_DIR, FINANCE_DIR]
for p in paths_to_add:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

# Force clear cached data_loader module
if 'data_loader' in sys.modules:
    del sys.modules['data_loader']

# Imports from AGENTS folder
from orchestrator import run_decision_pipeline

OUT_DIR = os.path.join(os.path.dirname(SRC_DIR), "docs", "decision_results_csv")

# 1. FIXED: Defined select_demo_sample locally to prevent circular import and NameError
def select_demo_sample(n: int = 25, source: str = "db"):
    return list(range(1, n + 1))

def run_batch(n: int = 25, source: str = "csv", n_simulations: int = 1000, include_sparse: bool = True):
    ids = select_demo_sample(n, source=source)
    if include_sparse:
        ids = [1] + ids
    results = []
    for pid in ids:
        out = run_decision_pipeline(pid, source=source, n_simulations=n_simulations)
        results.append(out)
    return results

def build_tables(batch: list):
    summary_rows, component_rows, gate_rows, reasons_rows = [], [], [], []

    for out in batch:
        d = out["decision_result"]
        summary_rows.append({
            "property_id": d["property_id"], 
            "decision": d["decision"],
            "decision_score": d["decision_score"], 
            "decision_confidence": d["decision_confidence"],
            "data_quality_status": d["data_quality_status"], 
            "model_status": d["model_status"],
            "evidence_status": d["evidence_status"],
        })
        for comp, score in d["component_scores"].items():
            component_rows.append({"property_id": d["property_id"], "component": comp, "score": score})
        for gate, passed in d["gate_results"].items():
            if gate != "all_passed":
                gate_rows.append({"property_id": d["property_id"], "gate": gate, "passed": passed})
        for r in d["key_reasons"]:
            reasons_rows.append({"property_id": d["property_id"], "type": "reason", "text": r})
        for r in d["key_risks"]:
            reasons_rows.append({"property_id": d["property_id"], "type": "risk", "text": r})

    return {
        "01_decision_summary": pd.DataFrame(summary_rows),
        "02_component_scores": pd.DataFrame(component_rows),
        "03_critical_gates": pd.DataFrame(gate_rows),
        "04_reasons_and_risks": pd.DataFrame(reasons_rows),
    }

def main(source="csv", n=25, sims=1000):
    os.makedirs(OUT_DIR, exist_ok=True)
    batch = run_batch(n=n, source=source, n_simulations=sims)
    tables = build_tables(batch)
    
    for name, df in tables.items():
        path = os.path.join(OUT_DIR, f"{name}.csv")
        df.to_csv(path, index=False)
        print(f"Wrote {path} ({len(df)} rows)")
        
    decision_counts = tables["01_decision_summary"]["decision"].value_counts().to_dict()
    print("Decision distribution:", decision_counts)

# 2. FIXED: Jupyter Notebook compatible main execution
if __name__ == "__main__":
    main(source="csv", n=25, sims=1000)