#!/usr/bin/env python
# coding: utf-8

# In[3]:


"""Renders models/model_registry.json into docs/model_registry.md (full Model Cards)."""
import json
import os

MODELS_DIR = os.path.join("..", "models")
DOCS_DIR = os.path.join("..", "docs")

def fmt_list(items):
    return "\n".join(f"- {i}" for i in items) if items else "- (none)"


def fmt_dict(d, indent=0):
    if d is None:
        return "n/a"
    lines = []
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"{'  '*indent}- **{k}**:")
            lines.append(fmt_dict(v, indent + 1))
        else:
            lines.append(f"{'  '*indent}- **{k}**: {v}")
    return "\n".join(lines)


def main():
    with open(os.path.join(MODELS_DIR, "model_registry.json")) as f:
        registry = json.load(f)

    order = [
        "valuation_v1_gbr", "rent_v1_gbr", "price_forecast_v1_gbr_6m",
        "demand_forecast_v1_gbr_6m", "dom_v1_gbr", "sale_probability_v1_gbr",
        "risk_score_v1_composite",
    ]

    out = ["# PHASE 4 — MODEL REGISTRY", "",
           "*Auto-generated from `models/model_registry.json`. Every field below traces directly "
           "to a computed result — nothing here is invented (Master Prompt Section 3.2).*", ""]

    out.append("## Summary Table\n")
    out.append("| Model | Target | Status | Version |")
    out.append("|---|---|---|---|")
    for name in order:
        e = registry[name]
        out.append(f"| `{name}` | {e['target'][:60]}{'...' if len(e['target'])>60 else ''} | "
                    f"**{e['status']}** | {e['version']} |")
    out.append("")

    for name in order:
        e = registry[name]
        out.append(f"---\n\n## `{e['model_name']}`\n")
        out.append(f"**Status: {e['status']}**  ·  **Version:** {e['version']}  ·  "
                    f"**Registered:** {e['registered_at_utc']}\n")
        out.append(f"**Target:** {e['target']}\n")
        out.append(f"**Features ({e['n_features']}):** {', '.join(e['features'][:25])}"
                    f"{' ...' if e['n_features'] > 25 else ''}\n")
        out.append(f"**Training data:** {e['training_data']}\n")
        out.append(f"**Validation method:** {e['validation_method']}\n")
        out.append("**Metrics:**\n")
        out.append(fmt_dict(e["metrics"]) + "\n")
        out.append("**Baseline comparison:**\n")
        out.append(fmt_dict(e["baseline"]) + "\n")
        out.append("**Limitations:**\n")
        out.append(fmt_list(e["limitations"]) + "\n")
        out.append(f"**Business use:** {e['business_use']}\n")
        out.append("**Known failure cases:**\n")
        out.append(fmt_list(e["known_failure_cases"]) + "\n")

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "model_registry.md"), "w") as f:
        f.write("\n".join(out))
    print("Wrote docs/model_registry.md")


if __name__ == "__main__":
    main()



# In[ ]:



