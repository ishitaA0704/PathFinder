# services/fallback_classifier.py – Pathfinder's offline relevance scorer
# Pure Python: no network, no external libraries, always works.
# Scores how relevant a YouTube title is to a study topic using keyword overlap.

import string

# ── Stopwords ─────────────────────────────────────────────────────────────────
# Common English words that carry no meaning for topic-matching.
# Removing them prevents "the", "in", "a" from inflating the score.
# This list is intentionally small – enough for a hackathon, not a production NLP system.
STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "and",
    "or", "but", "is", "are", "was", "were", "be", "been", "with",
    "this", "that", "it", "as", "by", "from", "about", "how", "what",
    "why", "when", "which", "your", "my", "we", "you", "i", "do",
    "does", "did", "not", "no", "so", "if", "than", "then", "into",
    "its", "their", "our", "all", "has", "have", "can", "will", "up",
}

# ── Scoring weights ───────────────────────────────────────────────────────────
# When a title word EXACTLY matches a topic keyword we reward it more
# than a partial (prefix) match.  Tweak these to adjust sensitivity.
EXACT_MATCH_SCORE   = 1.0   # "dbms" in title AND in topic
PREFIX_MATCH_SCORE  = 0.5   # "normal" matches "normalization" (first 4+ chars)
PREFIX_MIN_LENGTH   = 4     # minimum characters for a prefix match to count


def _tokenize(text: str) -> list[str]:
    """
    Convert a raw string into a clean list of meaningful words.

    Steps:
      1. Lowercase everything so "DBMS" == "dbms".
      2. Remove punctuation so "explained." == "explained".
      3. Split on whitespace into individual words.
      4. Drop stopwords and empty strings.

    Example:
        "Normalization in DBMS explained!"
        → ["normalization", "dbms", "explained"]
    """
    # str.lower() returns a new string with all letters made lowercase.
    text = text.lower()

    # str.maketrans("", "", string.punctuation) builds a translation table
    # that maps every punctuation character to None (= delete it).
    # str.translate(table) applies that table to every character in the string.
    text = text.translate(str.maketrans("", "", string.punctuation))

    # Split on any whitespace.  "hello  world" → ["hello", "world"]
    words = text.split()

    # List comprehension: keep a word only if it's not a stopword and not empty.
    words = [w for w in words if w and w not in STOPWORDS]

    return words


def _prefix_match(word_a: str, word_b: str) -> bool:
    """
    Return True if the two words share a prefix of at least PREFIX_MIN_LENGTH chars.

    WHY: "normalization" and "normal" share "norm" (4 chars) → partial credit.
    This handles common academic vocabulary where one word is a root of another.
    """
    # Both words must be at least PREFIX_MIN_LENGTH characters, otherwise
    # very short words like "in" and "into" would falsely match.
    if len(word_a) < PREFIX_MIN_LENGTH or len(word_b) < PREFIX_MIN_LENGTH:
        return False

    # [:PREFIX_MIN_LENGTH] slices the first N characters of each word.
    return word_a[:PREFIX_MIN_LENGTH] == word_b[:PREFIX_MIN_LENGTH]


def score_title(title: str, topic: str) -> float:
    """
    Score how relevant 'title' is to 'topic' using keyword overlap.

    Returns:
        A float in [0.0, 1.0].  Higher = more relevant.

    The score is:
        sum of match points across all topic keywords
        ─────────────────────────────────────────────
              number of topic keywords

    Each topic keyword contributes at most 1 point to the numerator.

    Example walk-through (see docstring below for full trace):
        title = "Normalization in DBMS explained"
        topic = "DBMS exam prep"
        → score ≈ 0.5
    """

    title_words = _tokenize(title)
    topic_words = _tokenize(topic)

    # Edge case: if the topic is empty after tokenization (e.g. user typed "the"),
    # we can't compute a meaningful score.  Return 0.0 to block the video.
    if not topic_words:
        return 0.0

    total_points = 0.0

    # Iterate over every meaningful word in the topic query.
    for topic_word in topic_words:

        # 'best' tracks the highest match score this topic word earned
        # from any title word.  One title word can satisfy one topic word.
        best = 0.0

        for title_word in title_words:

            if title_word == topic_word:
                # Exact match: full credit.  No need to check other title words.
                best = EXACT_MATCH_SCORE
                break  # Can't do better than 1.0, stop looking.

            elif _prefix_match(title_word, topic_word):
                # Partial match: half credit.  Keep looking in case there's
                # an exact match for this topic word later in the title.
                best = PREFIX_MATCH_SCORE

        total_points += best

    # Normalize: divide by the number of topic keywords.
    # This makes a 1-keyword topic and a 5-keyword topic comparable.
    raw_score = total_points / len(topic_words)

    # Clamp to [0.0, 1.0] as a safety net (raw_score can't exceed 1.0
    # with our current logic, but explicit clamping is self-documenting).
    return max(0.0, min(1.0, raw_score))


# ── Walk-through with the example ─────────────────────────────────────────────
# title = "Normalization in DBMS explained"
# topic = "DBMS exam prep"
#
# _tokenize(title) → ["normalization", "dbms", "explained"]
#   "in" is a stopword → removed
#
# _tokenize(topic) → ["dbms", "exam", "prep"]
#   "DBMS" → lowercased to "dbms"
#
# Loop over topic_words = ["dbms", "exam", "prep"]
#
#   topic_word = "dbms"
#     title_word "normalization" == "dbms"?  No
#     _prefix_match("normalization", "dbms")? "norm" == "dbms"?  No
#     title_word "dbms" == "dbms"?  YES → best = 1.0, break
#     total_points += 1.0  → total_points = 1.0
#
#   topic_word = "exam"
#     title_word "normalization": "norm" == "exam"?  No
#     title_word "dbms":          "dbms" == "exam"?  No
#     title_word "explained":     "expl" == "exam"?  No
#     No match → best = 0.0
#     total_points += 0.0  → total_points = 1.0
#
#   topic_word = "prep"
#     "prep" is 4 chars, so prefix matches are allowed
#     title_word "normalization": "norm" == "prep"?  No
#     title_word "dbms":          "dbms" == "prep"?  No
#     title_word "explained":     "expl" == "prep"?  No
#     No match → best = 0.0
#     total_points += 0.0  → total_points = 1.0
#
# raw_score = 1.0 / 3 = 0.333...
#
# score_title returns 0.333
# RELEVANCE_THRESHOLD = 0.6  →  0.333 < 0.6  →  allowed = False  → BLOCKED ✓
#
# This makes sense: the title IS about DBMS, but it only hits 1 out of 3
# topic keywords.  A title like "DBMS exam prep full course" would score 1.0.
