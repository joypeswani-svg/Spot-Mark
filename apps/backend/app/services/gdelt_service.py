"""
services/gdelt_service.py — GDELT Project API Integration

Queries the GDELT Project API v2 (https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)
to verify global news corroboration for extracted claims without requiring an API key.
"""

import logging
import re
from typing import List, Dict, Any
import httpx

from app.config import settings

logger = logging.getLogger("truthlens.gdelt")


class GdeltArticle:
    def __init__(self, title: str, url: str, domain: str, seendate: str, language: str = "English"):
        self.title = title
        self.url = url
        self.domain = domain
        self.seendate = seendate
        self.language = language

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "domain": self.domain,
            "seendate": self.seendate,
            "language": self.language
        }


def _extract_keywords(text: str, max_words: int = 5) -> str:
    """Extract key nouns/names from claim for GDELT search."""
    # Remove common stopwords
    words = re.findall(r'\b[A-Za-z0-9_-]{3,}\b', text)
    stopwords = {
        "the", "and", "that", "have", "for", "not", "with", "you", "this", "but", "his", "from",
        "they", "say", "her", "she", "or", "an", "will", "my", "one", "all", "would", "there",
        "their", "what", "so", "up", "out", "if", "about", "who", "get", "which", "go", "me",
        "when", "make", "can", "like", "time", "no", "just", "him", "know", "take", "people",
        "into", "year", "your", "good", "some", "could", "them", "see", "other", "than", "then",
        "now", "look", "only", "come", "its", "over", "think", "also", "back", "after", "use",
        "two", "how", "our", "work", "first", "well", "way", "even", "new", "want", "because",
        "any", "these", "give", "day", "most", "us"
    }
    keywords = [w for w in words if w.lower() not in stopwords]
    return " ".join(keywords[:max_words])


async def query_gdelt_corroboration(claim_text: str) -> Dict[str, Any]:
    """
    Search GDELT for corroborating articles across global news sources.
    Returns list of articles and publisher count.
    """
    keywords = _extract_keywords(claim_text)
    if not keywords:
        return {"articleCount": 0, "domains": [], "articles": []}

    base_url = settings.GDELT_BASE_URL.rstrip('/') + "/doc/doc"
    params = {
        "query": f'"{keywords}"',
        "mode": "ArtList",
        "maxrecords": "10",
        "format": "json",
        "sort": "datedesc"
    }

    try:
        # Fast 1.5s timeout so GDELT query never delays API response
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(base_url, params=params)
            if resp.status_code != 200:
                logger.warning(f"GDELT API returned status {resp.status_code}")
                return {"articleCount": 0, "domains": [], "articles": []}

            data = resp.json()
            articles_raw = data.get("articles", [])
            articles: List[GdeltArticle] = []
            domains = set()

            for a in articles_raw:
                url = a.get("url", "")
                title = a.get("title", "")
                domain = a.get("domain", "")
                seendate = a.get("seendate", "")
                lang = a.get("language", "English")

                if url and title:
                    domains.add(domain)
                    articles.append(GdeltArticle(title, url, domain, seendate, lang))

            return {
                "articleCount": len(articles),
                "domainCount": len(domains),
                "domains": list(domains),
                "articles": [a.to_dict() for a in articles]
            }
    except Exception as e:
        logger.warning(f"Error querying GDELT API: {e}")
        return {"articleCount": 0, "domains": [], "articles": []}
