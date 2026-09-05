# PHASE 4 — Predictive & Advanced Analytics
## Real Estate AI Decision Intelligence Platform

Yeh Phase 4 hai — Master A-Z Prompt ki 10-phase architecture (P1→P10) ka agla step, jo diye gaye Phase 1 (Data Foundation), Phase 2 (SQL BI), aur Phase 3 (EDA & Statistics) deliverables ke upar bana hai.

## Kya banaya gaya

7 candidate predictive models (Section 4.2 ke A–G), poore ML governance ke saath (leakage checks, temporal/holdout split, baseline comparison, model registry):

| Model | File | Target | Final Status |
|---|---|---|---|
| A — Property Valuation | `src/model_a_valuation.py` | `asking_price` | PASS WITH LIMITATIONS |
| B — Rent Prediction | `src/model_b_rent.py` | `monthly_rent` | PASS WITH LIMITATIONS |
| C — Price Forecast (6m) | `src/model_c_price_forecast.py` | locality `average_price_sqft`, +6m | CONDITIONAL (forced) |
| D — Demand Forecast (6m) | `src/model_d_demand_forecast.py` | locality `demand_index`, +6m | PASS WITH LIMITATIONS |
| E — Days on Market | `src/model_e_dom.py` | `days_on_market` | **REJECTED** |
| F — Sale Probability | `src/model_f_sale_probability.py` | Sold vs Expired/Withdrawn | **REJECTED** |
| G — Risk Score | `src/model_g_risk_score.py` | composite 0–100 risk score | UNCALIBRATED |

Poori detail ke liye padhein: **`docs/phase4_report.md`** (phase completion report), **`docs/model_registry.md`** (har model ka full card), **`docs/limitations.md`** (sab limitations ek jagah).

## Kaise chalayein

```bash
cd phase4
pip install -r requirements-phase4.txt --break-system-packages

# Sab 7 models ek saath train/compute karo (idempotent — dobara chalane se overwrite hoga, koi error nahi)
python3 src/train_all.py

# Model registry ko readable markdown me render karo
python3 src/render_registry_md.py

# 14 automated tests chalao
python3 src/test_phase4.py
```

## Data source

Yeh phase Phase 1 ke `data/processed/*.csv` files (already cleaned, validated data) se seedha padhta hai — `data/` folder me copy kiye gaye hain. Agar live PostgreSQL database available ho, to `src/data_loader.py` ko usse point kiya ja sakta hai bina kisi model script ko change kiye (join logic same rahegi).

## Zaroori governance decisions (summary)

1. **Model A aur B ek doosre ka target feature ke roop me use nahi karte** (asking_price ↔ monthly_rent), taaki circular leakage na ho — automated test se enforce kiya gaya hai.
2. **Model C ka status CONDITIONAL force kiya gaya hai**, uske metrics achhe hone ke bawajood, kyunki uska target column Phase 3 EDA me traced ek known data-generation bug (uncapped compounding) carry karta hai. Original generator script deliverables me nahi tha, isliye source par fix nahi ho saka — documented log-space fallback use kiya gaya.
3. **Model E aur F ko REJECT kiya gaya** kyunki independently verify karne par unka signal near-random nikla (yeh Phase 3 EDA ke findings ko confirm karta hai).
4. **Model D baseline (persistence) ko beat nahi kar paya**, isliye high R² ke bawajood usko PASS nahi diya gaya.
5. **Model G ek transparent, deterministic composite hai** (trained ML model nahi), REJECTED models (E, F) ko input ke roop me exclude karta hai, aur UNCALIBRATED status ke saath register hua hai kyunki real-world outcome se validate nahi kiya gaya.

## Folder structure

```
phase4/
├── data/                       # Phase 1 se copy kiya gaya processed data (read-only input)
├── src/                        # sab model scripts, data loader, governance utils, tests
├── models/                     # trained .joblib artifacts + model_registry.json
├── docs/                       # phase4_report.md, model_registry.md, limitations.md
├── requirements-phase4.txt
└── README_PHASE4.md            # yeh file
```

## Next phase dependency

Phase 5 (Evidence Intelligence & RAG) is phase par directly depend nahi karta. Phases 6/7/8 Model A/B/C/D/G ke outputs consume karenge jaisa `docs/phase4_report.md` Section 12 me likha hai. Phase 9 ka Prediction Agent `models/model_registry.json` load karke REJECTED models ko serve karne se mana karega.
