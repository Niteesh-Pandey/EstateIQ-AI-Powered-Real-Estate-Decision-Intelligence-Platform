"""
Phase 10B Chat -- Query Router
================================
Classifies a free-text question into one of five intents, BEFORE any
pipeline or LLM call is made. This replaces a single fragile regex (the
original chat script matched any bare 4-digit number as a property_id,
which misfires on years, percentages, or locality numbers, and had no
path at all for general/comparison/ranking questions).

Intents:
  PROPERTY   -- asking about one specific property (by id or a sentence
                containing one)
  COMPARE    -- asking to compare two or more specific properties
  LOCALITY   -- asking about a locality (by id or by name)
  RANKING    -- asking for a "best/top/safest/highest-return" list --
                answered by actually running the pipeline and sorting by
                the right metric, never by arbitrary file order
  GENERAL    -- a conceptual/definitional question about the platform
                itself, not tied to any specific property
  UNCLEAR    -- none of the above matched with reasonable confidence;
                the router refuses to guess (same "no silent guessing"
                principle used throughout this platform) and asks the
                user to rephrase, with examples

Each classification returns a structured dict, never just a label, so the
caller has everything it needs without re-parsing the query.
"""
import re

COMPARE_WORDS = re.compile(r"\bcompar|\bvs\.?\b|\bversus\b", re.IGNORECASE)
RANKING_WORDS = re.compile(
    r"\btop\b|\bbest\b|\brecommend|\bsuggest|\bsafest\b|\bhighest\b|\blowest\b|"
    r"\bshow me (some|a few)?\s*properties\b",
    re.IGNORECASE,
)
LOCALITY_WORDS = re.compile(r"\blocality\b|\bneighbou?rhood\b|\barea\b", re.IGNORECASE)
GENERAL_QUESTION_WORDS = re.compile(
    r"^\s*(what|why|how|explain|define|is|are|does|do|can|should i (know|understand))\b",
    re.IGNORECASE,
)
PROPERTY_NUMBER = re.compile(r"\b(\d{2,6})\b")
TOP_N = re.compile(r"\btop\s+(\d+)\b", re.IGNORECASE)


def _extract_numbers(text):
    return [int(m) for m in PROPERTY_NUMBER.findall(text)]


def classify(query: str) -> dict:
    q = (query or "").strip()
    if not q:
        return {"intent": "UNCLEAR", "reason": "Empty question."}

    numbers = _extract_numbers(q)

    # 1. Comparison -- "compare 2731 and 5053", "2731 vs 5053"
    if COMPARE_WORDS.search(q) and len(numbers) >= 2:
        return {"intent": "COMPARE", "property_ids": numbers[:5], "raw_query": q}

    # 2. Locality -- explicit "locality" keyword + a number, or the
    #    keyword alone (caller does a name lookup against localities.csv)
    if LOCALITY_WORDS.search(q):
        loc_id = numbers[0] if numbers else None
        return {"intent": "LOCALITY", "locality_id": loc_id, "raw_query": q}

    # 3. Ranking -- "top 5 properties", "best investment", "safest option"
    if RANKING_WORDS.search(q):
        n_match = TOP_N.search(q)
        n = int(n_match.group(1)) if n_match else 5
        criterion = "decision_score"
        if re.search(r"\bsafe|\blow(er)? risk|\bstab", q, re.IGNORECASE):
            criterion = "confidence"
        elif re.search(r"\breturn|\birr\b|\byield\b|\bprofit", q, re.IGNORECASE):
            criterion = "irr"
        return {"intent": "RANKING", "n": min(n, 15), "criterion": criterion, "raw_query": q}

    # 4. A single, plausible property id -- bare number, or a number
    #    embedded in an explicit "property ..." phrase. Deliberately
    #    stricter than the ranking/locality/compare checks above (which
    #    all run first), so "locality 32" or "compare 2731 and 5053"
    #    never falls through to here.
    if re.search(r"\bproperty\b", q, re.IGNORECASE) and numbers:
        return {"intent": "PROPERTY", "property_id": numbers[0], "raw_query": q}
    if re.fullmatch(r"\d{1,6}", q):
        return {"intent": "PROPERTY", "property_id": int(q), "raw_query": q}
    if len(numbers) == 1 and not GENERAL_QUESTION_WORDS.search(q):
        return {"intent": "PROPERTY", "property_id": numbers[0], "raw_query": q}

    # 5. General/conceptual question -- starts with a question word, or
    #    contains a "?", and has no property/locality reference at all
    if GENERAL_QUESTION_WORDS.search(q) or "?" in q:
        return {"intent": "GENERAL", "raw_query": q}

    # 6. Nothing matched with confidence -- ask, don't guess
    return {
        "intent": "UNCLEAR",
        "raw_query": q,
        "reason": "Could not confidently determine what you're asking. "
                  "Try a property id (e.g. '2731'), 'compare 2731 and 5053', "
                  "'top 5 properties', 'locality 32', or a general question "
                  "like 'why were some models rejected?'.",
    }
