"""
tests/test_step3.py — Integration and Unit Tests for Step 3 Pipeline
Tests claim extraction, Fact Check API fallback, GDELT search, and synthesizer logic.
"""

import pytest
import asyncio
from app.services.claim_extractor import extract_claims, extract_claims_heuristic
from app.services.gdelt_service import query_gdelt_corroboration, _extract_keywords
from app.services.synthesizer import analyze_and_synthesize_text


@pytest.mark.asyncio
async def test_claim_extraction_heuristic():
    text = (
        "NASA confirmed that Earth will experience 3 days of total darkness in December due to a solar storm. "
        "Scientists reported that the solar phenomenon occurs once every 1,000 years. "
        "However, official sources stated that the rumor was completely unfounded."
    )
    claims = extract_claims_heuristic(text)
    assert len(claims) > 0
    assert any("NASA" in c.claim or "darkness" in c.claim for c in claims)


@pytest.mark.asyncio
async def test_gdelt_keyword_extraction():
    claim = "Pope Francis surprised the world by endorsing Donald Trump for President"
    keywords = _extract_keywords(claim)
    assert "Pope" in keywords or "Francis" in keywords or "Trump" in keywords


@pytest.mark.asyncio
async def test_synthesizer_pipeline():
    text = (
        "Pope Francis surprised the world by endorsing Donald Trump for President. "
        "The announcement was allegedly made from the Vatican."
    )
    result = await analyze_and_synthesize_text(text, url="https://example.com/test-article")
    
    assert "credibility" in result
    assert "score" in result["credibility"]
    assert "band" in result["credibility"]
    assert "claims" in result
    assert len(result["claims"]) > 0
    assert result["claims"][0]["verdict"] in ["TRUE", "FALSE", "MISLEADING", "UNVERIFIED"]
