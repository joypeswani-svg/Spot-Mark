"""
routers/moderation.py — Report & Block Moderation Router with PIB Fact Check Escalation

Handles:
1. Community Misinformation Reporting (`POST /api/v1/report`)
2. PIB Fact Check (Government of India) Direct 1-Click Export (`GET /api/v1/report/pib-export`)
3. Personal Domain Blocklist Sync (`POST /api/v1/user/blocklist`, `GET /api/v1/user/blocklist`)
"""

import logging
from typing import List, Optional, Dict, Any
from urllib.parse import quote, urlparse
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger("truthlens.moderation")

router = APIRouter(prefix="/api/v1", tags=["moderation"])

# ── In-Memory Database Stores (Persist to Postgres in production) ────────────

_reports_db: List[Dict[str, Any]] = []
_user_blocklists: Dict[str, List[str]] = {}  # user_id -> [blocked_domains]
_global_report_counts: Dict[str, int] = {}    # domain -> report_count

# PIB Fact Check Official Escalation Contacts
PIB_WHATSAPP_NUMBER = "+918799711259"
PIB_EMAIL = "pibfactcheck@gmail.com"
PIB_PORTAL_URL = "https://factcheck.pib.gov.in"

# ── Pydantic Request / Response Schemas ──────────────────────────────────────

class ReportRequest(BaseModel):
    url: Optional[str] = None
    domain: Optional[str] = None
    claimText: Optional[str] = None
    reason: str = Field(
        ...,
        description="Reason: false_information | deepfake | clickbait | hate_speech | scam"
    )
    notes: Optional[str] = None
    userId: Optional[str] = "anonymous"


class BlocklistRequest(BaseModel):
    domain: str
    action: str = Field("block", description="action: block | unblock")
    userId: Optional[str] = "anonymous"


def _build_pib_export(claim_text: Optional[str], url: Optional[str], domain: Optional[str]) -> Dict[str, str]:
    """Generate 1-click WhatsApp, Email, and Portal escalation links for PIB Fact Check."""
    headline = claim_text or f"Suspicious content on {domain or url or 'web'}"
    source_ref = f"\nSource URL: {url}" if url else ""
    
    text_message = (
        f"Hello PIB Fact Check Team,\n\n"
        f"I would like to report suspected misinformation for verification:\n\n"
        f"Claim / Headline: \"{headline}\"{source_ref}\n\n"
        f"Reported via TruthLens Misinformation Detector."
    )
    
    encoded_msg = quote(text_message)
    whatsapp_url = f"https://wa.me/918799711259?text={encoded_msg}"
    
    subject = quote(f"Fact Check Request: {headline[:50]}...")
    mailto_url = f"mailto:{PIB_EMAIL}?subject={subject}&body={encoded_msg}"

    return {
        "pibWhatsAppUrl": whatsapp_url,
        "pibEmailUrl": mailto_url,
        "pibPortalUrl": PIB_PORTAL_URL,
        "whatsappNumber": PIB_WHATSAPP_NUMBER,
        "email": PIB_EMAIL,
        "formattedText": text_message,
    }


@router.post("/report")
async def submit_report(req: ReportRequest):
    """
    Submit a report for suspected fake news or manipulated content.
    Automatically increments domain report metrics and generates PIB Fact Check escalation links.
    """
    domain = req.domain
    if not domain and req.url:
        try:
            domain = urlparse(req.url).netloc.replace("www.", "")
        except Exception:
            pass

    report_id = f"rep-{len(_reports_db) + 1}"
    record = {
        "id": report_id,
        "url": req.url,
        "domain": domain,
        "claimText": req.claimText,
        "reason": req.reason,
        "notes": req.notes,
        "userId": req.userId,
    }
    _reports_db.append(record)

    if domain:
        _global_report_counts[domain] = _global_report_counts.get(domain, 0) + 1

    pib_links = _build_pib_export(req.claimText, req.url, domain)

    return {
        "success": True,
        "reportId": report_id,
        "message": "Report submitted successfully to TruthLens community review database.",
        "domainTotalReports": _global_report_counts.get(domain, 1) if domain else 1,
        "pibEscalation": pib_links,
    }


@router.get("/report/pib-export")
async def get_pib_export_links(
    claimText: Optional[str] = Query(None),
    url: Optional[str] = Query(None),
    domain: Optional[str] = Query(None)
):
    """
    Get 1-click PIB Fact Check export payloads (WhatsApp / Email / Web Portal) for a claim or URL.
    """
    return _build_pib_export(claimText, url, domain)


@router.post("/user/blocklist")
async def update_user_blocklist(req: BlocklistRequest):
    """
    Add or remove a domain from the user's personal blocklist.
    """
    user_id = req.userId or "anonymous"
    domain = req.domain.strip().lower().replace("www.", "")

    if not domain:
        raise HTTPException(status_code=400, detail="Invalid domain provided")

    user_list = _user_blocklists.setdefault(user_id, [])

    if req.action == "block":
        if domain not in user_list:
            user_list.append(domain)
        msg = f"Domain {domain} added to personal blocklist."
    elif req.action == "unblock":
        if domain in user_list:
            user_list.remove(domain)
        msg = f"Domain {domain} removed from personal blocklist."
    else:
        raise HTTPException(status_code=400, detail="Action must be 'block' or 'unblock'")

    return {
        "success": True,
        "action": req.action,
        "domain": domain,
        "message": msg,
        "blockedDomains": user_list,
    }


@router.get("/user/blocklist")
async def get_user_blocklist(userId: str = Query("anonymous")):
    """
    Retrieve user's personal domain blocklist.
    """
    return {
        "userId": userId,
        "blockedDomains": _user_blocklists.get(userId, []),
    }
