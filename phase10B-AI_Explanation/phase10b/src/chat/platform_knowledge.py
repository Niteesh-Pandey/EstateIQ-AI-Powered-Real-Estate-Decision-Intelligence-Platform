"""
Phase 10B Chat -- Platform Knowledge Base
============================================
A compact, hand-written summary of facts about THIS platform (architecture,
governance rules, decision formula, model statuses). Used to ground
general/conceptual questions ("what is IRR?", "why were models rejected?",
"how is the decision score calculated?") that are not about any specific
property.

This exists so general questions get an answer grounded in facts this
project actually established -- not the LLM's own general-purpose
knowledge of real estate, and not an invented number. When a live Gemini
call is made for a general question, this text is sent as context with an
instruction to answer only from it plus ordinary factual/definitional
knowledge, and to say so plainly if the platform-specific answer isn't in
this context. When no API key is available, relevant sections of this
text are shown directly.
"""

PLATFORM_KNOWLEDGE = """
ABOUT THIS PLATFORM
Real Estate AI Decision Intelligence Platform. A 10-phase pipeline that
turns raw property data into a governed investment decision:
Phase 1 Data Foundation -> Phase 2 SQL Business Intelligence -> Phase 3
EDA & Statistics -> Phase 4 Predictive Models -> Phase 5 Evidence/RAG ->
Phase 6 Financial Engine -> Phase 7 Monte Carlo Risk -> Phase 8 Geo
Intelligence -> Phase 9 Multi-Agent Decision Policy -> Phase 10 Power BI
+ AI Explanation Layer (this chat tool is part of Phase 10B).

CORE PRINCIPLE
Every number a user sees (IRR, NPV, decision score, ROI, risk metrics) is
produced by deterministic Python code -- never by an LLM. The AI
Explanation Layer (Gemini) is only allowed to explain and translate those
numbers into plain language. It cannot invent, round, or alter them. A
separate numeric-fidelity validator checks every LLM response against the
original numbers before it is shown to a user; if the LLM changes
anything, its response is discarded and a deterministic template is shown
instead.

THE DECISION SCORE FORMULA (Phase 9)
decision_score = 0.20*market_score + 0.15*prediction_score +
                  0.25*financial_score + 0.20*risk_score + 0.20*geo_score
(all five component scores are 0-100; weights are documented business
judgement, not statistically fitted). If a component is missing for a
property, its weight is redistributed proportionally across the other
available components rather than silently treated as zero.

DECISION SCORE vs DECISION CONFIDENCE (these are different things)
- decision_score: how strong the opportunity looks (0-100).
- decision_confidence: how much the platform trusts that score, based on
  data/model/evidence completeness (0-100). Risk completeness is
  hard-capped at 60/100 because Phase 7's Monte Carlo engine is
  UNCALIBRATED -- so decision_confidence can never fully trust the risk
  component, no matter how good the simulation looks.
A high score does NOT automatically mean high confidence.

DECISION STATES
INVEST (score >= 65 and confidence >= 55), AVOID (score <= 35), HOLD
(everything in between, including high-score-but-low-confidence cases),
INSUFFICIENT (a critical gate failed -- missing data, blocked evidence, or
confidence too low to make any call at all).

MACHINE LEARNING MODELS (Phase 4) -- 7 built, 2 REJECTED
- Model A (property valuation): PASS WITH LIMITATIONS, R^2 ~0.80
- Model B (rent prediction): PASS WITH LIMITATIONS, R^2 ~0.65
- Model C (6-month price forecast): CONDITIONAL -- a known data-generation
  bug in the training data's price-growth series was found and disclosed
- Model D (demand forecast): PASS WITH LIMITATIONS
- Model E (days-on-market): REJECTED -- independently confirmed R^2
  approx 0, i.e. no better than guessing the average
- Model F (sale-probability): REJECTED -- ROC-AUC approx 0.52, barely
  above random chance (0.50)
- Model G (risk score, deterministic composite, not ML): UNCALIBRATED
Rejected models are never used by the Prediction Agent, by design -- a
governance rule enforced in code, not just policy.

MONTE CARLO RISK SIMULATION (Phase 7)
Every probability, VaR, and CVaR figure comes from a Monte Carlo
simulation whose input distributions are documented judgement calls, not
fitted to real historical outcomes. This is why every such figure is
labeled UNCALIBRATED throughout the platform -- it is a useful relative
signal, not a real-world probability guarantee.

KNOWN, DISCLOSED DATA GAPS
- Flood/environmental risk data is unavailable for all localities in this
  dataset -- shown as "INSUFFICIENT DATA", never estimated.
- Transit and commercial accessibility scores only exist where the
  underlying infrastructure records exist for that category.
- 13 of 90 localities have an unreliable appreciation CAGR (>20%/yr,
  traced to a data-generation artifact) and are excluded from being used
  as a default appreciation assumption.

FINANCIAL METRICS USED (Phase 6)
Gross/net yield, cap rate, NOI, cash-on-cash return, IRR, NPV, DSCR,
payback period, ROI (total, over the holding period -- defined as net
profit / equity invested, NOT gross cash received / equity invested).
Scenarios: Severe Downside, Downside, Base, Upside.

WHAT THIS CHAT TOOL CAN DO
- Explain a specific property's decision (give a property ID, or a
  sentence containing one).
- Rank/recommend properties from the platform's demo sample by decision
  score, IRR, or confidence ("top 5 properties", "safest investment",
  "best returns").
- Answer general questions about how the platform works, using this
  knowledge base.
- Compare two or more properties side by side.
It CANNOT answer questions about properties or localities outside the
loaded dataset, and it never fabricates a number that isn't in the
platform's own output.
"""
