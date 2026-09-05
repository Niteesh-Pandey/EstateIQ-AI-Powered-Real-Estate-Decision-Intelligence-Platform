# PHASE 5 — Evidence Intelligence & RAG
## Real Estate AI Decision Intelligence Platform

Phase 4 (Predictive & Advanced Analytics) ke baad ka agla step — Master A-Z Prompt ki 10-phase architecture me Phase 5. Yeh phase Phase 3 ke code-structure convention ko exactly follow karta hai (live PostgreSQL via `db/connection.py`, `src/<topic>/*.py` modules, do orchestrators — Markdown report aur numbered CSV export — plus chart PNGs).

## Kya banaya gaya

| Module | Kaam | Master Prompt Section |
|---|---|---|
| `evidence_registry.py` | Evidence Registry (120 documents, `ai.documents` se) | 5.3 |
| `chunking.py` | Sentence-aware chunking, document relationships | 5.4 |
| `lexical_retrieval.py` | BM25 (keyword-based) | 5.5 |
| `semantic_retrieval.py` | LSA (offline semantic signal — transformer embedding NAHI) | 5.5 |
| `hybrid_retrieval.py` | BM25 + LSA combine, metadata filtering | 5.5 |
| `reranking.py` | Source quality + recency + query alignment | 5.6 |
| `grounding.py` | Citation ID validation, claim validation, coverage | 5.7 |
| `prompt_injection.py` | 11-pattern injection/authority-spoofing detector | 5.8 |
| `observability.py` | Query/latency/zero-result-rate logging | 5.9 |
| `rag_evaluation.py` | 6 question categories | 5.10 |

Poori detail: **`docs/phase5_report.md`** (phase completion report — re-check me mile 3 bugs bhi documented hain), **`docs/limitations.md`**.

## Kaise chalayein

### Live database ke saath (production path — jaisa Phase 3 aapke local environment me chala)

```bash
cd phase5
pip install -r requirements-phase5.txt --break-system-packages
export DB_USER=...
export DB_PASSWORD=...

python3 src/evidence/generate_evidence_report.py     # docs/evidence_report.md
python3 src/evidence/export_results_csv.py           # docs/evidence_results_csv/*.csv
python3 src/evidence/generate_charts.py              # docs/evidence_charts/*.png
```

### Local re-check (bina database ke — jo maine yahan use kiya)

```bash
python3 src/evidence/generate_evidence_report.py --source csv
python3 src/evidence/export_results_csv.py --source csv
python3 src/evidence/generate_charts.py --source csv
python3 src/evidence/test_phase5.py                  # 27 automated tests
```

`--source csv` `data/processed/documents.csv` se padhta hai — yeh wahi rows hain jo `ai.documents` table me load hui thi. Isliye dono paths (`db` aur `csv`) same evidence registry content produce karte hain — sirf transport alag hai.

## Re-check me kya mila (important)

Maine sirf modules likh kar chhoda nahi — poora pipeline real 120-document data par chalaya aur test kiya. Isme **3 real bugs mile aur fix kiye**:

1. Grounding module citation marker (`[ev_1_0]`) ke andar ke numbers (1, 0) ko galti se "claim" samajh raha tha — fix kiya.
2. Report generator ka demo text banane wala code `.` par naive split kar raha tha, jo decimal numbers (jaise `59.9`) ko bhi tod raha tha — fix kiya.
3. Citation ko sentence ke period ke baad append karne se ek alag "orphan sentence" ban raha tha jisme citation tha par claim nahi — fix kiya.

Poori detail `docs/phase5_report.md` Section 8 me hai. Fix ke baad **27/27 tests pass**.

## Folder structure

```
phase5/
├── data/processed/       # documents.csv (120 rows) + supporting tables
├── db/connection.py      # Phase 1/3 se unchanged — env-var based Postgres pool
├── src/evidence/         # 10 core modules + 3 orchestrator scripts + tests
├── docs/                 # report, limitations, 8 CSVs, 4 charts
├── requirements-phase5.txt
└── README_PHASE5.md
```

## Next phase dependency

Phases 6/7/8 (Financial, Risk, Geo) is phase par strictly depend nahi karte, par optionally is phase ki grounding API use kar sakte hain evidence cite karne ke liye. Phase 9 ka Evidence Agent aur Evidence Validator seedha `hybrid_retrieval.py`, `reranking.py`, `grounding.py`, `prompt_injection.py` import karenge.
