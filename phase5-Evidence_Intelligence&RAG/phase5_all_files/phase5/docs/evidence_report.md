# Real Estate Platform -- Evidence Intelligence & RAG Report

*Generated 2026-09-04 10:26 (source=csv, status=csv_dev_mode, database=data/processed/documents.csv). Master A-Z Prompt, Phase 5.*

## 1. Evidence Registry

- Evidence items loaded: **120** (from 120 source documents)
- Mean source confidence: **0.692**
- Date range: 2024-08-22 to 2026-08-15
- By source type: {'INTERNAL_RESEARCH': 37, 'DEVELOPER_FILING': 36, 'NEWS': 29, 'MARKET_REPORT': 18}
- By raw source: {'Internal Research': 37, 'Developer Filing': 36, 'News': 29, 'Market Report': 18}

## 2. Chunking

- Total chunks: **120** from 120 documents (1.00 chunks/doc avg, max 1)
- Mean chunk length: 221 characters
- Note: at this dataset's current document length (~221 chars avg), chunking is a documented no-op (1 chunk/doc). The sentence-aware splitter is unit-tested separately against a synthetic long document -- see `test_phase5.py`.

## 3. Hybrid Retrieval (BM25 + LSA)

**Query:** `infrastructure connectivity Pune` (filters={'city': 'Pune'})
- `ev_35_0` rerank=0.8376 | News | Infrastructure Update — Balay Layout, Pune
- `ev_72_0` rerank=0.7544 | Developer Filing | Infrastructure Update — Garg Enclave, Pune
- `ev_1_0` rerank=0.3565 | Internal Research | Infrastructure Update — Shanker Gardens, Pune

**Query:** `developer track record`
- `ev_20_0` rerank=0.8225 | News | Developer Report — Tata Hills, Pune
- `ev_21_0` rerank=0.7516 | News | Developer Report — Tata Hills, Pune
- `ev_37_0` rerank=0.6235 | Internal Research | Developer Report — Dugar Layout, Hyderabad

**Query:** `nonexistent gibberish query zzqx`
- *(0 results -- correctly returns empty, not invented)*

**Retrieval observability summary:** {'n_calls': 3, 'zero_result_rate_pct': 33.3, 'mean_latency_ms': 21.957, 'p95_latency_ms': 7.45, 'mean_result_count': 3.33}

## 4. Grounding Validation

- **well_grounded** -> status=`PASS`, unsupported_claims=0, unknown_ids=[]
- **hallucinated_citation** -> status=`BLOCKED`, unsupported_claims=0, unknown_ids=['ev_999999_0']

## 5. Prompt Injection Scan

- Documents flagged in live evidence registry: **0** / 120 (expected 0 for this clean synthetic dataset)
- Detector is separately verified against a 5-case adversarial test set in `test_phase5.py` (3 malicious, 2 clean -- all classified correctly).

## 6. RAG Evaluation (6 question categories)

- Pass rate: **100.0%** (5/5 scored cases)
  - `direct`: pass=True, n_results=8
  - `paraphrased`: pass=True, n_results=8
  - `ambiguous`: pass=True, n_results=8
  - `no_answer`: pass=True, n_results=0
  - `conflicting_evidence`: pass=True, n_results=8
  - `unsupported`: pass=None, n_results=0

## 7. Governance Summary

| Component | Status |
|---|---|
| Evidence Registry | PASS |
| Chunking | PASS |
| Hybrid Retrieval | PASS |
| Grounding Validator | PASS |
| Prompt Injection Guard | PASS |
| RAG Evaluation | PASS |

*Full limitations: see `docs/limitations.md`.*