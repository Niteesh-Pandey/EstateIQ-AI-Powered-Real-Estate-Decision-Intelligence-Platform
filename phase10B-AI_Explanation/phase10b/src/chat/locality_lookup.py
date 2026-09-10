"""
Phase 10B Chat -- Locality Lookup
===================================
Resolves a locality reference (numeric id, or a name typed by the user)
against data/processed/localities.csv, and finds which of the platform's
demo-sample properties fall in it (via properties -> projects ->
localities). The original chat script only supported a bare numeric
locality id; this adds name matching, since a person is far more likely
to type "Shanker Gardens" than "locality 32".
"""
import os
import difflib

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(os.path.dirname(_HERE), "..", "data", "processed")


def _load(name):
    return pd.read_csv(os.path.join(_DATA_DIR, f"{name}.csv"))


def resolve_locality(locality_id=None, name_hint: str = None) -> dict:
    """Returns {"found": bool, "locality_id", "locality_name", "city_name",
    "scores": {...}} or {"found": False, "suggestions": [...]} if a name
    hint didn't match closely enough -- never silently picks a locality
    the user didn't mean."""
    localities = _load("localities")
    cities = _load("cities")
    df = localities.merge(cities[["city_id", "city_name"]], on="city_id", how="left")

    row = None
    if locality_id is not None:
        match = df[df["locality_id"] == locality_id]
        if not match.empty:
            row = match.iloc[0]
    elif name_hint:
        name_hint_clean = name_hint.strip().lower()
        exact = df[df["locality_name"].str.lower() == name_hint_clean]
        if not exact.empty:
            row = exact.iloc[0]
        else:
            contains = df[df["locality_name"].str.lower().str.contains(name_hint_clean, na=False)]
            if len(contains) == 1:
                row = contains.iloc[0]
            elif len(contains) > 1:
                return {"found": False,
                        "suggestions": contains["locality_name"].tolist()[:8],
                        "reason": f"Multiple localities match '{name_hint}' -- please be more specific."}
            else:
                close = difflib.get_close_matches(name_hint, df["locality_name"].tolist(), n=5, cutoff=0.5)
                return {"found": False, "suggestions": close,
                        "reason": f"No locality found matching '{name_hint}'."}

    if row is None:
        return {"found": False, "suggestions": [], "reason": "No locality id or name provided."}

    return {
        "found": True,
        "locality_id": int(row["locality_id"]),
        "locality_name": row["locality_name"],
        "city_name": row["city_name"],
        "scores": {
            "connectivity_score": row["connectivity_score"],
            "safety_score": row["safety_score"],
            "infrastructure_score": row["infrastructure_score"],
            "development_score": row["development_score"],
            "commercial_score": row["commercial_score"],
        },
    }


def properties_in_locality(locality_id: int, limit: int = 10) -> list:
    props = _load("properties")
    projects = _load("projects")
    merged = props.merge(projects[["project_id", "locality_id"]], on="project_id", how="left")
    matched = merged[merged["locality_id"] == locality_id]
    return matched["property_id"].head(limit).tolist()


def format_locality_summary(info: dict, property_ids: list) -> str:
    if not info["found"]:
        msg = info["reason"]
        if info["suggestions"]:
            msg += "\nDid you mean: " + ", ".join(info["suggestions"]) + "?"
        return msg

    s = info["scores"]
    lines = [
        f"{info['locality_name']}, {info['city_name']} (locality_id={info['locality_id']})",
        f"Connectivity {s['connectivity_score']} | Safety {s['safety_score']} | "
        f"Infrastructure {s['infrastructure_score']} | Development {s['development_score']} | "
        f"Commercial {s['commercial_score']}  (each 0-100)",
    ]
    if property_ids:
        lines.append(f"\n{len(property_ids)} properties found in this locality: "
                      f"{', '.join(str(p) for p in property_ids)}")
        lines.append(f"Ask about any of these ids for a full decision explanation.")
    else:
        lines.append("\nNo properties from this locality are in the platform's loaded dataset.")
    return "\n".join(lines)
