"""
Phase 10B Chat -- General Q&A
===============================
Answers conceptual/definitional questions about the platform itself
("what is IRR?", "why were models rejected?", "how is the decision score
calculated?") -- questions the original chat script had NO path for at
all (it always tried to resolve a property_id, defaulting to the first
row of the CSV for anything it didn't understand, which is silently
wrong for a question that isn't about a specific property in the first
place).

Reuses ai_explanation_layer's low-level Gemini call (_call_gemini_raw) so
there is exactly one place in the codebase that talks to the Gemini API.
Grounds every answer in platform_knowledge.PLATFORM_KNOWLEDGE -- the
model is instructed to answer from that context (plus ordinary factual/
definitional knowledge for terms like "IRR"), and to say plainly when
something isn't covered by this platform's own documentation, rather than
inventing a platform-specific detail that was never established.
"""
import os
import sys
import urllib.error

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "explanation"))
from ai_explanation_layer import _call_gemini_raw  # noqa: E402
from platform_knowledge import PLATFORM_KNOWLEDGE  # noqa: E402

GENERAL_QA_SYSTEM_PROMPT = f"""You are the general-question assistant for a real estate investment decision platform.

Below is the platform's own knowledge base -- facts specifically established by this project (architecture, formulas, model statuses, known data gaps).

{PLATFORM_KNOWLEDGE}

Rules:
1. Answer the user's question using the platform knowledge base above wherever it's relevant.
2. You may also use your own general knowledge for ordinary factual/definitional questions (e.g. "what is IRR" as a financial concept) -- but if the user is asking about how THIS platform specifically works and the answer isn't in the knowledge base above, say plainly that this platform's documentation doesn't cover that, rather than inventing a specific number or rule.
3. Never state a specific number (a score, a percentage, a count) about this platform unless it appears in the knowledge base above.
4. Keep answers concise and in plain business language -- a few short paragraphs at most, not an essay.
5. This is a general question, not about any specific property -- do not invent or reference a specific property_id.
"""


def answer_general_question(question: str, api_key: str = None) -> dict:
    """Returns {"answer": str, "source": "llm"|"knowledge_base_fallback",
    "fallback_reason": str|None}."""
    api_key = api_key or os.environ.get("GEMINI_API_KEY")

    if not api_key:
        return {
            "answer": _fallback_from_knowledge_base(question),
            "source": "knowledge_base_fallback",
            "fallback_reason": "No GEMINI_API_KEY available -- showing the platform's own "
                                "documentation directly rather than attempting a live answer.",
        }

    try:
        answer = _call_gemini_raw(GENERAL_QA_SYSTEM_PROMPT, question, api_key)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as e:
        return {
            "answer": _fallback_from_knowledge_base(question),
            "source": "knowledge_base_fallback",
            "fallback_reason": f"Gemini API call failed ({type(e).__name__}: {e}) -- showing the "
                                "platform's own documentation directly instead.",
        }

    return {"answer": answer, "source": "llm", "fallback_reason": None}


def _fallback_from_knowledge_base(question: str) -> str:
    """Without an LLM, we cannot do free-form reasoning over the question --
    so rather than pretend to answer, this returns the full knowledge base
    with a clear pointer, which is honest about what it can and can't do
    offline."""
    return (
        "I can't make a live Gemini call right now, so here is the platform's own "
        "documentation in full -- your question is likely answered somewhere below:\n"
        + PLATFORM_KNOWLEDGE
    )
