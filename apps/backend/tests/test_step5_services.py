"""
tests/test_step5_services.py — Unit tests for Step 5 Domain Reputation & Writing-Style Classifier
"""

import pytest
from app.services.domain_reputation import lookup_domain, get_domain_score
from app.services.style_classifier import classify_writing_style, get_style_score


def test_domain_reputation_known():
    res = lookup_domain("https://www.bbc.com/news/articles/12345")
    assert res["domain"] == "bbc.com"
    assert res["factuality"] == "high"
    assert res["credibilityScore"] == 92
    assert res["isSatire"] is False


def test_domain_reputation_subdomain_fallback():
    res = lookup_domain("edition.cnn.com")
    assert res["credibilityScore"] == 72
    assert res["factuality"] == "mostly-factual"


def test_domain_reputation_satire():
    res = lookup_domain("https://theonion.com/article-title")
    assert res["isSatire"] is True
    assert res["credibilityScore"] == 50


def test_domain_reputation_unknown():
    res = lookup_domain("https://random-unknown-blog-1234.net/article")
    assert res["factuality"] == "unknown"
    assert res["credibilityScore"] == 60  # Neutral fallback


def test_style_classifier_clean_text():
    clean_text = (
        "The World Health Organization confirmed today that new guidelines for vaccination have been updated. "
        "According to Dr. Smith, extensive clinical trials conducted across three continents showed strong efficacy. "
        "The complete study was published in the Lancet medical journal earlier this week."
    )
    result = classify_writing_style(clean_text)
    assert result["score"] >= 80
    assert any("Good source attribution" in f for f in result["findings"])


def test_style_classifier_clickbait_sensational():
    clickbait_text = (
        "YOU WON'T BELIEVE WHAT HAPPENED NEXT!!! EXPOSED! "
        "THEY DON'T WANT YOU TO KNOW THE TRUTH ABOUT THIS SHOCKING DISCOVERY! "
        "Everyone is outraged and furious! Share before this gets deleted by authorities! "
        "Sources say experts claim this is the worst event in history!"
    )
    result = classify_writing_style(clickbait_text)
    assert result["score"] < 50
    assert any("Clickbait" in f for f in result["findings"])
    assert any("ALL CAPS" in f for f in result["findings"])
    assert any("Emotionally charged" in f for f in result["findings"])
