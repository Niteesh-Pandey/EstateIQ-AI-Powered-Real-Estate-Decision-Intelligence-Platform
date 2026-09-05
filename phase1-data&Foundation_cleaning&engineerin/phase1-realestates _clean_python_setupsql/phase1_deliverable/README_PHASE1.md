# PHASE 1 — Data Engineering (Complete ✅)

Yeh phase karta kya hai, seedhe shabdon mein:
1. Ek **synthetic (fake but realistic) real-estate dataset** generate karta hai — 14 tables, ~90,000 rows — jisme real business logic hai (achhi locality → zyada price, oversupply → zyada days-on-market, etc.), random noise nahi.
2. Us data ko **validate** karta hai — duplicate IDs, missing links (orphan foreign keys), galat values (negative price, out-of-range demand) — sab check hota hai.
3. Us data ko apke **local PostgreSQL** mein load karta hai, taaki Phase 2 (SQL Analytics) usse query kar sake.

Maine already isko run karke check kiya hai (is sandbox mein) — **validation 100% clean pass hui**: 0 duplicate primary keys, 0 orphan foreign key rows, 0 negative price/area, sab ranges sahi. Report `docs/validation_report.md` mein hai.

---

## Step 0 — Prerequisites (ek baar install karna hai)

- Python 3.10+ (aapke paas already hai)
- PostgreSQL 14+ installed aur running (`psql --version` se check karein)
  - Windows: [postgresql.org/download/windows](https://www.postgresql.org/download/windows/)
  - Mac: `brew install postgresql@14`
  - Linux: `sudo apt install postgresql`
- pgvector extension (baad mein RAG/Phase 5 ke liye chahiye, abhi optional hai — agar `CREATE EXTENSION vector;` fail ho to schema file se woh line hata sakte hain for now)

---

## Step 1 — Project folder set karein

Is zip ko apne `real-estate-ai/` project folder ke andar extract karein (ya agar naya start kar rahe hain, isi ko root bana lein). Structure yeh hona chahiye:

```
real-estate-ai/
├── data/
│   ├── generate_data.py
│   ├── generate_data_part2.py
│   └── raw/            ← CSVs already generated hain isi mein
├── src/
│   └── validate_data.py
├── sql/
│   ├── 00_create_database.sql
│   ├── 01_schema.sql
│   └── 02_load_data.sql
├── docs/
│   ├── data_dictionary.md
│   └── validation_report.md
└── requirements-phase1.txt
```

## Step 2 — Python environment banayein

```bash
cd real-estate-ai
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements-phase1.txt
```

## Step 3 — Data generate karein (reproducible, seed=42)

Data pehle se `data/raw/` mein maujood hai (maine verify kiya hai), lekin agar aap **fresh regenerate** karna chahte hain apne machine par:

```bash
python data/generate_data.py
python data/generate_data_part2.py
```

Isse 14 CSV files banengi `data/raw/` mein — `cities.csv`, `localities.csv`, `developers.csv`, `projects.csv`, `properties.csv`, `transactions.csv`, `rentals.csv`, `listing_history.csv`, `property_events.csv`, `expenses.csv`, `infrastructure.csv`, `market_monthly.csv`, `economic_monthly.csv`, `documents.csv`.

Seed fixed hai (42) — matlab jitni baar chalayenge, **same data** banega. Isse reproducibility milti hai (professional project ki nishani).

## Step 4 — Data validate karein

```bash
python src/validate_data.py
```

Yeh check karta hai:
- Row counts sahi hain
- Koi duplicate ID nahi (e.g. do properties same property_id ke saath)
- Koi orphan foreign key nahi (e.g. koi transaction jiska property hi na ho)
- Price/area/demand jaise columns ke ranges sahi hain (negative price nahi, demand 0-100 ke beech)
- Outliers kitne % hain

Result terminal par print hoga aur `docs/validation_report.md` mein save bhi ho jayega. **Agar kahin bhi "0" ke alawa koi number dikhe duplicate/orphan/violation mein, tabhi hi aage badhna hai — abhi sab 0 hai, so aap safe hain.**

## Step 4.5 — Data CLEAN karein (raw → processed)

Yeh naya step hai: `src/clean_data.py` raw CSVs ko clean karke `data/processed/` mein naya, clean version bana deta hai. Raw data ko kabhi touch/overwrite nahi karta — raw hamesha original rehta hai, processed usse cleaned version hai.

```bash
python src/clean_data.py
```

Yeh kya karta hai, step by step (sab terminal par print hota hai + `docs/cleaning_report.md` mein save bhi hota hai):

1. **Text columns trim** — extra spaces hata deta hai
2. **Dates ko real date type mein convert** — abhi text (`"2024-01-15"`) hai, ab proper date ban jata hai jisse aage sorting/filtering aasan hogi
3. **Duplicate rows/IDs hatana** — agar koi duplicate ho (abhi 0 hain, but production mein aa sakte hain)
4. **Orphan rows hatana** — agar koi row apne parent table se link na ho paaye
5. **Missing values fill karna** — `properties.monthly_rent` mein 160 (2%) missing values the; unhe usi property_type + bedrooms group ke **median rent** se fill kiya, aur ek naya column `monthly_rent_was_imputed` (True/False) add kiya taaki pata rahe kaunsi values asli hain aur kaunsi guess ki gayi hain
6. **Outliers flag karna (delete nahi)** — bahut zyada/kam price wali rows ko delete nahi karte (ho sakta hai woh real luxury property ho), balki ek naya column jaise `asking_price_is_outlier` (True/False) add karte hain — Phase 3/4 mein aap decide kar sakte hain unhe include karna hai ya nahi

**Output:** `data/processed/*.csv` — same 14 files, same column names + kuch naye flag columns, ab clean.

Verify karne ke liye:
```bash
python -c "import pandas as pd; df = pd.read_csv('data/processed/properties.csv'); print(df.isnull().sum())"
```
`monthly_rent` mein ab 0 nulls dikhne chahiye.

> Aage ke phases (Phase 2 SQL, Phase 3 EDA) mein hum `data/processed/` wali files use karenge, `data/raw/` wali nahi — raw sirf audit trail ke liye rakhi jaati hai.

## Step 5 — PostgreSQL database banayein

```bash
psql -U postgres -f sql/00_create_database.sql
```

Isse `real_estate_db` naam ka database aur `real_estate_app` naam ka user ban jayega. (Password change kar lein `00_create_database.sql` mein `change-this-password` ki jagah apna real password.)

## Step 6 — Schema (empty tables) banayein

```bash
psql -U postgres -d real_estate_db -f sql/01_schema.sql
```

Agar `CREATE EXTENSION vector;` par error aaye ("extension vector is not available"), to abhi ke liye woh line `sql/01_schema.sql` se comment (`--`) kar dein — pgvector sirf Phase 5 (RAG) mein chahiye hoga, Phase 1-4 ke liye zaroori nahi.

## Step 7 — CSV data ko PostgreSQL mein load karein

**Zaroori:** yeh command project ke **root folder** se hi chalayein (jahan `data/` folder dikh raha ho), kyunki `02_load_data.sql` relative path use karta hai.

```bash
cd real-estate-ai   # root folder, agar wahan nahi hain
psql -U postgres -d real_estate_db -f sql/02_load_data.sql
```

## Step 8 — Verify karein ki data andar aa gaya

```bash
psql -U postgres -d real_estate_db -c "SELECT count(*) FROM core.properties;"
```

Output `8000` aana chahiye. Aap yeh bhi try kar sakte hain:

```sql
psql -U postgres -d real_estate_db
\dt core.*                          -- saari tables list karega
SELECT * FROM core.cities LIMIT 5;  -- data dekhein
```

---

## Phase 1 Checklist ✅

- [x] 14 relational tables, ~90K rows, real business logic (random noise nahi)
- [x] Reproducible generation (seed=42)
- [x] Full validation: 0 duplicate PKs, 0 orphan FKs, 0 range violations
- [x] PostgreSQL schema with proper types + foreign keys (`sql/01_schema.sql`)
- [x] Data dictionary (`docs/data_dictionary.md`) — har column ka matlab documented
- [x] Data PostgreSQL mein load hone ke liye ready

**Phase 1 complete hai.** Jab aap confirm kar dein ki apke local Postgres mein data load ho gaya (Step 8 ka `8000` output aa gaya), tab Phase 2 (SQL Analytics — window functions, locality ranking, comparables) shuru karte hain.

Agar kahin bhi koi error aaye (psql not found, connection refused, extension missing, etc.) — woh exact error message mujhe bhejein, main us hisaab se fix bata dunga.
