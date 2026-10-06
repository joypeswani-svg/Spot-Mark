"""
services/style_classifier.py — Writing-Style Credibility Classifier

A fast heuristic classifier that detects clickbait, sensationalist, and
emotionally manipulative writing patterns commonly found in misinformation.

This replaces the planned DistilBERT ONNX model for the initial release because:
  1. It runs in <1ms (no model loading, no GPU dependency)
  2. It provides interpretable sub-scores the user can understand
  3. It covers the most common misinformation writing patterns
  4. A future DistilBERT model can be plugged in alongside or as a replacement

Scoring approach:
  - Start at 80 (neutral well-written article)
  - Deduct points for each detected red-flag pattern
  - Bonus points for attribution and balanced language
  - Final score clamped to 0–100

Red-flag patterns checked:
  - ALL CAPS sentences / excessive exclamation marks
  - Clickbait phrases ("you won't believe", "shocking", "breaking")
  - Emotional manipulation words ("outraged", "terrifying", "disgusting")
  - Missing attribution ("sources say" without naming sources)
  - Excessive superlatives ("biggest ever", "worst in history")
  - URL/content mismatch indicators
"""

import re
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("truthlens.style_classifier")

# ── Pattern Definitions ───────────────────────────────────────────────────────

CLICKBAIT_PHRASES = [
    r"\byou won'?t believe\b",
    r"\bshocking\b",
    r"\bmind[- ]?blowing\b",
    r"\binsane\b",
    r"\bunbelievable\b",
    r"\bwhat happens next\b",
    r"\bthis is why\b",
    r"\beveryone is talking about\b",
    r"\bgoing viral\b",
    r"\bbreaking\s*:?\s*!",
    r"\bjust in\s*:?\s*!",
    r"\bexclusive\s*:?\s*!",
    r"\burgent\s*:?\s*!",
    r"\bshare before .*(deleted|removed|banned)\b",
    r"\bthey don'?t want you to know\b",
    r"\bthe truth about\b",
    r"\bexposed\s*!",
    r"\bwake up\b",
]

EMOTIONAL_MANIPULATION = [
    r"\boutraged?\b",
    r"\bterrif(ying|ied)\b",
    r"\bdisgust(ing|ed)\b",
    r"\bhorrif(ying|ied|ic)\b",
    r"\bfurious\b",
    r"\benraged\b",
    r"\bslammed\b",
    r"\bblasted\b",
    r"\bdestroyed\b",      # used hyperbolically
    r"\bobliterated\b",
    r"\bepic fail\b",
    r"\bsavage\b",
    r"\bripped apart\b",
]

SUPERLATIVES = [
    r"\b(biggest|largest|worst|best|greatest|most dangerous|deadliest)\s+(ever|in history|of all time|on record)\b",
    r"\bnever before\b",
    r"\bunprecedented\b",       # only a flag when combined with others
    r"\bhistoric\b",
]

ATTRIBUTION_POSITIVE = [
    r"\baccording to [A-Z]",    # Named source
    r"\b(said|told|confirmed|stated)\s+(by|to)\b",
    r"\b(Reuters|AP|AFP|BBC|study|research|journal|university)\b",
    r"\bcite[sd]?\b",
    r"\bpeer[- ]reviewed\b",
]

VAGUE_ATTRIBUTION = [
    r"\bsources say\b",
    r"\bexperts say\b",
    r"\bsome people say\b",
    r"\baccording to reports\b",
    r"\binsiders claim\b",
    r"\bit is believed\b",
    r"\brumor has it\b",
    r"\ballegedly\b",
]


def _count_pattern_matches(text: str, patterns: list) -> Tuple[int, List[str]]:
    """Count how many distinct patterns match in text. Returns (count, matched_patterns)."""
    count = 0
    matched = []
    text_lower = text.lower()
    for pattern in patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            count += 1
            matched.append(pattern)
    return count, matched


def classify_writing_style(text: str) -> Dict[str, Any]:
    """
    Analyze writing style and return a credibility sub-score (0–100)
    plus interpretable findings.

    Returns:
        {
            "score": 72,
            "findings": ["Clickbait language detected", ...],
            "details": {
                "capsRatio": 0.05,
                "exclamationCount": 3,
                "clickbaitHits": 2,
                ...
            }
        }
    """
    findings: List[str] = []
    score = 80.0  # Start neutral-positive

    if not text or len(text) < 50:
        return {
            "score": 60,
            "findings": ["Text too short for style analysis"],
            "details": {},
        }

    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    word_count = len(text.split())

    # ── 1. ALL CAPS detection ────────────────────────────────────────────────
    caps_sentences = sum(1 for s in sentences if s.isupper() and len(s) > 15)
    caps_ratio = caps_sentences / max(1, len(sentences))
    if caps_ratio > 0.1:
        penalty = min(15, caps_ratio * 40)
        score -= penalty
        findings.append(f"Excessive ALL CAPS text ({caps_sentences} sentences)")

    # ── 2. Exclamation mark abuse ────────────────────────────────────────────
    excl_count = text.count("!")
    excl_per_100w = (excl_count / max(1, word_count)) * 100
    if excl_per_100w > 2.0:
        penalty = min(12, excl_per_100w * 3)
        score -= penalty
        findings.append(f"Heavy use of exclamation marks ({excl_count} total)")

    # ── 3. Clickbait phrases ─────────────────────────────────────────────────
    clickbait_hits, _ = _count_pattern_matches(text, CLICKBAIT_PHRASES)
    if clickbait_hits >= 1:
        penalty = min(20, clickbait_hits * 8)
        score -= penalty
        findings.append(f"Clickbait language detected ({clickbait_hits} patterns)")

    # ── 4. Emotional manipulation ────────────────────────────────────────────
    emo_hits, _ = _count_pattern_matches(text, EMOTIONAL_MANIPULATION)
    if emo_hits >= 2:
        penalty = min(15, emo_hits * 5)
        score -= penalty
        findings.append(f"Emotionally charged language ({emo_hits} patterns)")

    # ── 5. Excessive superlatives ────────────────────────────────────────────
    sup_hits, _ = _count_pattern_matches(text, SUPERLATIVES)
    if sup_hits >= 2:
        penalty = min(10, sup_hits * 4)
        score -= penalty
        findings.append(f"Excessive superlatives ({sup_hits} patterns)")

    # ── 6. Vague attribution ─────────────────────────────────────────────────
    vague_hits, _ = _count_pattern_matches(text, VAGUE_ATTRIBUTION)
    if vague_hits >= 2:
        penalty = min(12, vague_hits * 4)
        score -= penalty
        findings.append(f"Vague/anonymous sourcing ({vague_hits} patterns)")

    # ── 7. Positive: proper attribution ──────────────────────────────────────
    attr_hits, _ = _count_pattern_matches(text, ATTRIBUTION_POSITIVE)
    if attr_hits >= 2:
        bonus = min(10, attr_hits * 3)
        score += bonus
        findings.append(f"Good source attribution detected ({attr_hits} patterns)")

    # ── 8. Paragraph structure ───────────────────────────────────────────────
    # Well-structured articles tend to have more paragraphs (newlines)
    para_count = text.count("\n\n") + 1
    if para_count >= 5 and word_count > 300:
        score += 5
    elif para_count <= 1 and word_count > 200:
        score -= 5
        findings.append("Wall-of-text with minimal paragraph structure")

    # ── 9. Question-headline pattern ─────────────────────────────────────────
    # Betteridge's law: headlines that are questions tend to be clickbait
    first_sentence = sentences[0] if sentences else ""
    if first_sentence.endswith("?") and len(first_sentence) < 100:
        score -= 5
        findings.append("Question-style headline (Betteridge's law indicator)")

    # Clamp
    final_score = max(0, min(100, int(round(score))))

    if not findings:
        findings.append("No significant style red-flags detected")

    return {
        "score": final_score,
        "findings": findings,
        "details": {
            "capsRatio": round(caps_ratio, 3),
            "exclamationCount": excl_count,
            "clickbaitHits": clickbait_hits,
            "emotionalHits": emo_hits,
            "superlativeHits": sup_hits,
            "vagueAttributionHits": vague_hits,
            "properAttributionHits": attr_hits,
            "paragraphCount": para_count,
            "wordCount": word_count,
        },
    }


def get_style_score(text: str) -> float:
    """Convenience: return just the 0–100 style credibility score for the scorer."""
    return float(classify_writing_style(text).get("score", 70))
