"""
Phase 10B Chat -- Automated Tests
===================================
Run with: python3 test_chat.py (from the phase10b root, same folder as
chat.py) -- or python3 -m pytest test_chat.py -q if pytest is available.

Covers the query router's classification for every intent, the ranking
module's real sort behavior (including the decision-quality-first fix),
locality name/id resolution, and end-to-end answer() calls for each path
-- all against the real demo-sample data (--source csv), no mocking
needed except where an actual Gemini response is being simulated.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "src", "chat"))
sys.path.insert(0, os.path.join(_HERE, "src", "agents"))
sys.path.insert(0, os.path.join(_HERE, "src", "explanation"))

from query_router import classify
from ranking import rank_properties
from locality_lookup import resolve_locality, properties_in_locality
import chat as chat_module


# ------------------------------------------------------------------ router

def test_router_bare_number_is_property():
    r = classify("2731")
    assert r["intent"] == "PROPERTY" and r["property_id"] == 2731


def test_router_sentence_with_property_word_is_property():
    r = classify("Should I invest in property 4021?")
    assert r["intent"] == "PROPERTY" and r["property_id"] == 4021


def test_router_compare_detects_two_ids():
    r = classify("compare 2731 and 5053")
    assert r["intent"] == "COMPARE" and r["property_ids"] == [2731, 5053]


def test_router_vs_syntax_also_detected():
    r = classify("2731 vs 5053")
    assert r["intent"] == "COMPARE"


def test_router_ranking_default_n_is_5():
    r = classify("best properties")
    assert r["intent"] == "RANKING" and r["n"] == 5


def test_router_ranking_explicit_n():
    r = classify("top 3 properties")
    assert r["intent"] == "RANKING" and r["n"] == 3


def test_router_ranking_criterion_safest_maps_to_confidence():
    r = classify("safest investment")
    assert r["intent"] == "RANKING" and r["criterion"] == "confidence"


def test_router_ranking_criterion_returns_maps_to_irr():
    r = classify("highest returns")
    assert r["intent"] == "RANKING" and r["criterion"] == "irr"


def test_router_locality_by_id():
    r = classify("locality 32")
    assert r["intent"] == "LOCALITY" and r["locality_id"] == 32


def test_router_locality_by_name_has_no_id():
    r = classify("locality Shanker Gardens")
    assert r["intent"] == "LOCALITY" and r["locality_id"] is None


def test_router_general_question_word():
    r = classify("why were some ML models rejected?")
    assert r["intent"] == "GENERAL"


def test_router_unclear_does_not_crash_or_guess():
    r = classify("blah random gibberish")
    assert r["intent"] == "UNCLEAR"
    assert "reason" in r


def test_router_empty_query_is_unclear():
    r = classify("")
    assert r["intent"] == "UNCLEAR"


def test_router_compare_needs_two_or_more_numbers():
    """A stray 'compare' with only one number should NOT be treated as a
    comparison -- there is nothing to compare against."""
    r = classify("compare 2731")
    assert r["intent"] != "COMPARE"


# ----------------------------------------------------------------- ranking

def test_ranking_returns_requested_count():
    rows = rank_properties(n=3, criterion="decision_score")
    assert len(rows) <= 3


def test_ranking_is_sorted_by_requested_criterion_within_decision_tier():
    rows = rank_properties(n=10, criterion="irr")
    invest_rows = [r for r in rows if r["decision"] == "INVEST"]
    irrs = [r["irr"] for r in invest_rows if r["irr"] is not None]
    assert irrs == sorted(irrs, reverse=True)


def test_ranking_excludes_insufficient():
    rows = rank_properties(n=25, criterion="decision_score")
    assert all(r["decision"] != "INSUFFICIENT" for r in rows)


def test_ranking_prioritizes_decision_quality_over_raw_metric():
    """Regression test for a real bug found during manual testing: a
    'safest investment' (criterion=confidence) query surfaced an AVOID
    property with negative IRR ahead of genuine INVEST properties, purely
    because its decision_confidence happened to tie the top score. INVEST
    properties must always rank above AVOID properties regardless of the
    chosen secondary metric."""
    rows = rank_properties(n=25, criterion="confidence")
    decisions_seen = [r["decision"] for r in rows]
    if "AVOID" in decisions_seen and "INVEST" in decisions_seen:
        last_invest_idx = max(i for i, d in enumerate(decisions_seen) if d == "INVEST")
        first_avoid_idx = min(i for i, d in enumerate(decisions_seen) if d == "AVOID")
        assert last_invest_idx < first_avoid_idx, (
            "an AVOID property was ranked ahead of an INVEST property"
        )


# ------------------------------------------------------------- locality

def test_locality_resolve_by_id():
    info = resolve_locality(locality_id=32)
    assert info["found"] is True
    assert info["locality_name"]


def test_locality_resolve_by_exact_name():
    info = resolve_locality(name_hint="Shanker Gardens")
    assert info["found"] is True
    assert info["locality_id"] == 41


def test_locality_resolve_by_partial_name():
    info = resolve_locality(name_hint="Shanker")
    assert info["found"] is True
    assert info["locality_name"] == "Shanker Gardens"


def test_locality_unknown_name_returns_suggestions_not_a_guess():
    info = resolve_locality(name_hint="Nonexistent Place That Does Not Exist")
    assert info["found"] is False


def test_properties_in_locality_returns_a_list():
    ids = properties_in_locality(32)
    assert isinstance(ids, list)


# --------------------------------------------------------------- end-to-end

def test_e2e_property_query_does_not_crash():
    result = chat_module.answer("2731")
    assert "2731" in result


def test_e2e_nonexistent_property_returns_insufficient_not_crash():
    result = chat_module.answer("9999")
    assert "INSUFFICIENT" in result or "not found" in result


def test_e2e_ranking_query_returns_real_results():
    result = chat_module.answer("top 3 properties")
    assert "Property" in result


def test_e2e_locality_query_returns_real_results():
    result = chat_module.answer("locality 32")
    assert "locality_id=32" in result


def test_e2e_unclear_query_asks_rather_than_guesses():
    result = chat_module.answer("asdkjfh qwoeiru")
    assert "rephrase" in result.lower() or "understand" in result.lower() or "confidently" in result.lower()


def test_e2e_compare_query():
    result = chat_module.answer("compare 2731 and 5053")
    assert "2731" in result and "5053" in result


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_") and callable(obj)]
    passed, failed = 0, []
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed.append(t.__name__)
        except Exception as e:
            print(f"ERROR {t.__name__}: {e}")
            failed.append(t.__name__)
    print(f"\n{passed}/{len(tests)} passed.")
    if failed:
        print("Failed:", failed)
        sys.exit(1)
