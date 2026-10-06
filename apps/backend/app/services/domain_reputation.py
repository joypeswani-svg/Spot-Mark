"""
services/domain_reputation.py — Domain Reputation Lookup Service

Loads a curated CSV of domain → credibility/bias/factuality ratings at startup,
then provides O(1) lookups by domain name.

Data modeled after Media Bias/Fact Check methodology:
  - factuality:  very-high | high | mostly-factual | mixed | low | very-low | satire
  - bias:        center | center-left | center-right | left | right | far-left | far-right | …
  - credibility_score: 0–100 integer
  - ownership:   public-media | corporate | state-media | independent | nonprofit | …
  - is_satire:   true/false

Unknown domains get a neutral score (60) with "unknown" factuality.
"""

import csv
import logging
import os
from typing import Dict, Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger("truthlens.domain_reputation")

# ── In-memory domain reputation store ─────────────────────────────────────────

_domain_db: Dict[str, Dict[str, Any]] = {}
_loaded = False

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "domain_reputation.csv")


def _load_csv() -> None:
    """Load the CSV dataset into memory. Called once at first lookup."""
    global _loaded
    if _loaded:
        return

    resolved = os.path.abspath(CSV_PATH)
    if not os.path.exists(resolved):
        logger.warning(f"Domain reputation CSV not found at {resolved}. All lookups will return 'unknown'.")
        _loaded = True
        return

    try:
        with open(resolved, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                domain = row.get("domain", "").strip().lower()
                if not domain:
                    continue
                _domain_db[domain] = {
                    "domain": domain,
                    "factuality": row.get("factuality", "unknown"),
                    "bias": row.get("bias", "unknown"),
                    "credibilityScore": int(row.get("credibility_score", "60")),
                    "ownership": row.get("ownership", "unknown"),
                    "isSatire": row.get("is_satire", "false").lower() == "true",
                    "notes": row.get("notes", ""),
                }
        logger.info(f"Loaded {len(_domain_db)} domain reputation entries from CSV.")
    except Exception as e:
        logger.error(f"Failed to load domain reputation CSV: {e}")

    _loaded = True


def _normalize_domain(url_or_domain: str) -> str:
    """
    Extract and normalize the domain from a URL or bare domain string.
    Strips 'www.' prefix so www.bbc.com and bbc.com match the same entry.
    """
    d = url_or_domain.strip().lower()
    if "://" in d:
        try:
            d = urlparse(d).netloc
        except Exception:
            pass
    # Strip port
    if ":" in d:
        d = d.split(":")[0]
    # Strip www.
    if d.startswith("www."):
        d = d[4:]
    return d


def lookup_domain(url_or_domain: str) -> Dict[str, Any]:
    """
    Look up a domain's reputation.

    Returns a dict with:
      - domain: normalized domain string
      - factuality: very-high | high | mostly-factual | mixed | low | very-low | satire | unknown
      - bias: center | center-left | center-right | left | right | far-left | far-right | …
      - credibilityScore: 0–100
      - ownership: corporate | state-media | independent | nonprofit | …
      - isSatire: boolean
      - notes: human-readable note

    Unknown domains return a neutral credibilityScore of 60 and "unknown" factuality.
    """
    _load_csv()

    domain = _normalize_domain(url_or_domain)

    if domain in _domain_db:
        return _domain_db[domain]

    # Try parent domain (e.g., news.bbc.co.uk → bbc.co.uk)
    parts = domain.split(".")
    if len(parts) > 2:
        parent = ".".join(parts[1:])
        if parent in _domain_db:
            return _domain_db[parent]
        # For .co.uk style TLDs, try two levels up
        if len(parts) > 3:
            grandparent = ".".join(parts[2:])
            if grandparent in _domain_db:
                return _domain_db[grandparent]

    # Unknown domain — neutral score, never a false positive/negative
    return {
        "domain": domain,
        "factuality": "unknown",
        "bias": "unknown",
        "credibilityScore": 60,
        "ownership": "unknown",
        "isSatire": False,
        "notes": "Domain not in TruthLens reputation database. Score is neutral — not a verdict.",
    }


def get_domain_score(url_or_domain: str) -> float:
    """Convenience: return just the 0–100 credibility score for the scorer."""
    return float(lookup_domain(url_or_domain).get("credibilityScore", 60))
