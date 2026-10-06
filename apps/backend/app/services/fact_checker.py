"""
services/fact_checker.py — Google Fact Check Tools API Integration

Queries Google's Fact Check Tools API (https://developers.google.com/fact-check/tools/api)
to search for existing professional fact checks (Snopes, PolitiFact, Reuters, AP, etc.)
for extracted claims.
"""

import logging
from typing import List, Dict, Any, Optional
import httpx

from app.config import settings

logger = logging.getLogger("truthlens.fact_checker")

FACT_CHECK_API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


class FactCheckMatch:
    def __init__(
        self,
        publisher: str,
        title: str,
        url: str,
        textual_rating: str,
        claim_date: Optional[str] = None,
        review_date: Optional[str] = None
    ):
        self.publisher = publisher
        self.title = title
        self.url = url
        self.textual_rating = textual_rating
        self.claim_date = claim_date
        self.review_date = review_date

    def to_dict(self) -> Dict[str, Any]:
        return {
            "publisher": self.publisher,
            "title": self.title,
            "url": self.url,
            "textualRating": self.textual_rating,
            "claimDate": self.claim_date,
            "reviewDate": self.review_date
        }


async def search_google_fact_check(claim_text: str, language: str = "en") -> List[FactCheckMatch]:
    """
    Query Google Fact Check Tools API for matching fact-check articles.
    """
    api_key = settings.GOOGLE_FACT_CHECK_API_KEY
    if not api_key or api_key == "your_fact_check_api_key_here":
        logger.info("Google Fact Check API key not configured.")
        return []

    params = {
        "query": claim_text,
        "key": api_key,
        "languageCode": language,
        "pageSize": 5
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(FACT_CHECK_API_URL, params=params)
            if resp.status_code != 200:
                logger.warning(f"Google Fact Check API returned {resp.status_code}")
                return []

            data = resp.json()
            claims_data = data.get("claims", [])
            matches: List[FactCheckMatch] = []

            for item in claims_data:
                reviews = item.get("claimReview", [])
                for rev in reviews:
                    publisher_name = rev.get("publisher", {}).get("name", "Unknown Fact Checker")
                    review_title = rev.get("title") or item.get("text") or "Fact Check Review"
                    review_url = rev.get("url", "")
                    rating = rev.get("textualRating", "Unverified")
                    review_date = rev.get("reviewDate")
                    claim_date = item.get("claimDate")

                    if review_url:
                        matches.append(FactCheckMatch(
                            publisher=publisher_name,
                            title=review_title,
                            url=review_url,
                            textual_rating=rating,
                            claim_date=claim_date,
                            review_date=review_date
                        ))

            return matches
    except Exception as e:
        logger.warning(f"Error querying Google Fact Check API: {e}")
        return []
