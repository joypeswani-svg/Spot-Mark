"""
services/scorer.py — Composite Credibility Scoring Engine

Calculates composite credibility scores (0–100) using weighted sub-scores:
- Claim Verification (50%): Aggregate verdict of extracted claims
- Domain Reputation (20%): Outlet history & factuality rating
- Writing-Style Classifier (15%): Clickbait / emotional bias signals
- Cross-Corroboration (15%): Independent coverage count in global media
"""

import logging
from typing import List, Dict, Any, Tuple

from app.config import settings

logger = logging.getLogger("truthlens.scorer")


def calculate_composite_score(
    claim_verdict_scores: List[float],
    domain_rep_score: float = 75.0,
    style_classifier_score: float = 75.0,
    corroboration_ratio: float = 0.5,
    has_false_claims: bool = False,
    has_misleading_claims: bool = False,
) -> Dict[str, Any]:
    """
    Calculate 0–100 composite credibility score, band, color token, and explanation.
    Guarantees that unverified news without explicitly debunked FALSE claims
    never falls into the red 'likely-false' bucket.
    """
    if claim_verdict_scores:
        claim_verification_score = sum(claim_verdict_scores) / len(claim_verdict_scores)
    else:
        claim_verification_score = 75.0  # Default to neutral plausible

    cross_corroboration_score = min(100.0, max(0.0, corroboration_ratio * 100.0))

    # Weighted calculation
    raw_score = (
        (claim_verification_score * settings.SCORE_WEIGHT_CLAIM_VERIFICATION) +
        (domain_rep_score * settings.SCORE_WEIGHT_DOMAIN_REPUTATION) +
        (style_classifier_score * settings.SCORE_WEIGHT_STYLE_CLASSIFIER) +
        (cross_corroboration_score * settings.SCORE_WEIGHT_CROSS_CORROBORATION)
    )

    final_score = max(0, min(100, int(round(raw_score))))

    # Safety Guardrail: Never assign "likely-false" (Red) unless at least one claim is explicitly FALSE or MISLEADING
    if not has_false_claims and not has_misleading_claims:
        final_score = max(65, final_score)  # Floor score to 65 (Caution / Verified)

    if final_score >= settings.BAND_GREEN_MIN:
        band = "verified"
        color = "green"
        explanation = "Claims are independently corroborated by credible sources and media coverage."
    elif final_score >= settings.BAND_YELLOW_MIN:
        band = "caution"
        color = "yellow"
        explanation = "Claims are unverified or from mixed sources. Exercise normal judgment."
    else:
        band = "likely-false"
        color = "red"
        explanation = "Multiple factual claims contradict documented fact-checks from verified sources."

    return {
        "score": final_score,
        "band": band,
        "color": color,
        "explanation": explanation,
        "breakdown": {
            "claimVerification": round(claim_verification_score, 1),
            "domainReputation": round(domain_rep_score, 1),
            "styleClassifier": round(style_classifier_score, 1),
            "crossCorroboration": round(cross_corroboration_score, 1),
        }
    }
