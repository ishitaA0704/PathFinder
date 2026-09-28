# services/gemini_client.py – Pathfinder's online relevance scorer
# Calls the Gemini API and returns a float between 0.0 and 1.0.
# If ANYTHING goes wrong, raises GeminiUnavailableError so the caller
# can fall back to the local classifier without crashing.

import os

import google.generativeai as genai

# ── Constants ────────────────────────────────────────────────────────────────

# "flash" models are small and fast – ideal for a quick relevance check.
# Keeping the name here means you only change one line if Google releases
# a newer model.
GEMINI_MODEL = "gemini-3.8-flash"

# How many seconds to wait for Gemini before giving up.
# 15 s is long enough for the API on a good connection, short enough
# that the extension doesn't leave the user waiting forever.
GEMINI_TIMEOUT_SECONDS = 15


# ── Custom exception ─────────────────────────────────────────────────────────

class GeminiUnavailableError(Exception):
    """
    Raised whenever Gemini can't give us a usable score.

    Having a CUSTOM exception type (instead of letting random exceptions
    bubble up) means app.py can write:

        except GeminiUnavailableError:
            ...

    and be confident it is ONLY catching Gemini problems, not bugs in
    unrelated code.  Plain 'except Exception' would swallow everything.
    """
    pass


# ── Main function ─────────────────────────────────────────────────────────────

def get_gemini_score(title: str, topic: str) -> float:
    """
    Ask Gemini how relevant 'title' is to studying 'topic'.

    Returns:
        A float in [0.0, 1.0].  Higher = more relevant.

    Raises:
        GeminiUnavailableError: on missing API key, network error,
                                timeout, rate limit, or bad response.
    """

    # ── Step 1: get the API key ───────────────────────────────────────────────
    api_key = os.environ.get("GEMINI_API_KEY")

    # If the key is missing or still the placeholder value, fail fast.
    # We raise BEFORE making any network call to save time.
    if not api_key or api_key == "your_gemini_api_key_here":
        raise GeminiUnavailableError("GEMINI_API_KEY is not set or is still the placeholder value.")

    # ── Step 2: configure the SDK ─────────────────────────────────────────────
    # We use transport="rest" because the default gRPC transport can sometimes
    # hang or timeout when running inside a Flask multi-threaded environment.
    genai.configure(api_key=api_key, transport="rest")

    # ── Step 3: build the prompt ──────────────────────────────────────────────
    # We ask for ONLY a number so that parsing is trivial.
    prompt = (
        f"You are a study assistant. A student is focusing on the topic: '{topic}'.\n"
        f"Rate how relevant this YouTube video title is to their study session:\n"
        f"Title: '{title}'\n\n"
        f"Scoring rules:\n"
        f"- Score 0.8–1.0: directly about the topic (lectures, tutorials, explanations, exam prep)\n"
        f"- Score 0.5–0.7: loosely related (study strategies, adjacent concepts)\n"
        f"- Score 0.0–0.4: unrelated (entertainment, news, vlogs, gaming, music)\n\n"
        f"Reply with ONLY a single decimal number between 0 and 1. No words, no explanation."
    )

    # ── Step 4: call the API inside a try/except ──────────────────────────────
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        
        response = model.generate_content(
            prompt,
            request_options={"timeout": GEMINI_TIMEOUT_SECONDS}
        )

        # response.text is the raw string the model returned, e.g. "0.87\n"
        raw_text = response.text

    except Exception as e:
        # Catch everything: network errors, auth errors, timeout, SDK bugs.
        # We wrap the original error message so we can log it if needed,
        # but we always raise GeminiUnavailableError upward.
        raise GeminiUnavailableError(f"Gemini API call failed: {e}") from e

    # ── Step 5: parse the reply safely ────────────────────────────────────────
    # Even if the call succeeded, the model might return "0.9 (relevant)" or
    # empty text.  We parse defensively inside another try/except.
    try:
        # strip() removes leading/trailing whitespace and newlines.
        score = float(raw_text.strip())

        # Clamp to [0.0, 1.0] in case the model returns 1.05 or -0.1.
        # max(0.0, ...) ensures no negatives; min(1.0, ...) caps at 1.
        score = max(0.0, min(1.0, score))

    except (ValueError, AttributeError) as e:
        # ValueError: float("relevant") fails.
        # AttributeError: raw_text is None (model returned empty response).
        raise GeminiUnavailableError(
            f"Could not parse Gemini response as a float: '{raw_text}'"
        ) from e

    return score
