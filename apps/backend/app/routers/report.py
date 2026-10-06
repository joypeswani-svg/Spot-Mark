"""
routers/report.py — Misinformation Reporting API + PIB Fact Check Direct Escalation

Endpoints:
- POST /api/report: Submit report, generate evidence summary & 1-click PIB/IFCN escalation links
- GET /api/report/pib-export: Format custom claim into PIB WhatsApp / Email / Portal payloads
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from urllib.parse import quote, urlparse
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter()

# In-memory report storage (Postgres table in production)
_reports_store: List[Dict[str, Any]] = []

# Official PIB Fact Check Contact Info (Government of India)
PIB_WHATSAPP = "+918799711259"
PIB_EMAIL = "pibfactcheck@gmail.com"
PIB_PORTAL = "https://factcheck.pib.gov.in"

PLATFORM_REPORT_URLS = {
    "facebook":  "https://www.facebook.com/help/181495968648557",
    "twitter":   "https://help.twitter.com/en/rules-and-policies/twitter-report-violation",
    "youtube":   "https://support.google.com/youtube/answer/2802027",
    "instagram": "https://help.instagram.com/192435014247952",
    "tiktok":    "https://support.tiktok.com/en/safety-hq/report-a-problem",
    "whatsapp":  "https://faq.whatsapp.com/general/security-and-privacy/how-to-report-a-contact-or-group",
}


class ReportRequest(BaseModel):
    contentUrl: Optional[str] = None
    claimText: Optional[str] = None
    categories: List[str] = Field(default_factory=lambda: ["false_information"])
    analysisJobId: Optional[str] = None
    platform: Optional[str] = None
    notes: Optional[str] = None


class ReportLink(BaseModel):
    label: str
    url: str
    type: str = Field("external", description="external | pib_whatsapp | pib_email | pib_portal")
    notes: Optional[str] = None


class ReportResponse(BaseModel):
    reportId: str
    summary: str
    reportLinks: List[ReportLink]
    pibEscalation: Dict[str, str]


def build_pib_export_payload(claim_text: Optional[str], content_url: Optional[str]) -> Dict[str, str]:
    """Build 1-click WhatsApp, Email, and Web Portal export links for PIB Fact Check."""
    headline = (claim_text or "Suspicious news report").strip()
    url_ref = f"\nSource URL: {content_url}" if content_url else ""
    
    formatted_msg = (
        f"Hello PIB Fact Check Team (Govt of India),\n\n"
        f"I would like to report suspected misinformation for verification:\n\n"
        f"Claim / Headline: \"{headline}\"{url_ref}\n\n"
        f"Reported via TruthLens Misinformation Detector."
    )
    
    encoded_text = quote(formatted_msg)
    wa_url = f"https://wa.me/918799711259?text={encoded_text}"
    
    subj = quote(f"PIB Fact Check Request: {headline[:45]}...")
    email_url = f"mailto:{PIB_EMAIL}?subject={subj}&body={encoded_text}"

    return {
        "pibWhatsAppUrl": wa_url,
        "pibEmailUrl": email_url,
        "pibPortalUrl": PIB_PORTAL,
        "whatsappNumber": PIB_WHATSAPP,
        "email": PIB_EMAIL,
        "formattedText": formatted_msg,
    }


@router.post("/report", response_model=ReportResponse)
async def generate_and_submit_report(request: ReportRequest):
    """
    Submit a report for suspected fake news or manipulated content.
    Generates an evidence summary and direct 1-click escalation links to:
      1. PIB Fact Check (Govt of India) via WhatsApp / Email / Portal
      2. Social Platform safety pages
      3. IFCN (International Fact-Checking Network)
    """
    report_id = f"rep-{uuid.uuid4().hex[:8]}"
    domain = None
    if request.contentUrl:
        try:
            domain = urlparse(request.contentUrl).netloc.replace("www.", "")
        except Exception:
            pass

    record = {
        "reportId": report_id,
        "contentUrl": request.contentUrl,
        "domain": domain,
        "claimText": request.claimText,
        "categories": request.categories,
        "notes": request.notes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _reports_store.append(record)

    summary = (
        f"Report #{report_id} registered. Content at {request.contentUrl or 'submitted snippet'} "
        f"flagged for [{', '.join(request.categories)}]. Evidence logged for community review."
    )

    pib_links = build_pib_export_payload(request.claimText, request.contentUrl)

    report_links = [
        ReportLink(
            label="🏛️ Submit to PIB Fact Check (WhatsApp)",
            url=pib_links["pibWhatsAppUrl"],
            type="pib_whatsapp",
            notes="Direct WhatsApp message to official Govt of India PIB Fact Check desk (+91 8799711259)"
        ),
        ReportLink(
            label="📧 Email PIB Fact Check Desk",
            url=pib_links["pibEmailUrl"],
            type="pib_email",
            notes="Send formatted email report to pibfactcheck@gmail.com"
        ),
        ReportLink(
            label="🌐 PIB Fact Check Portal",
            url=pib_links["pibPortalUrl"],
            type="pib_portal",
            notes="Submit directly via official portal at factcheck.pib.gov.in"
        ),
    ]

    if request.platform and request.platform.lower() in PLATFORM_REPORT_URLS:
        report_links.append(ReportLink(
            label=f"Report on {request.platform.title()}",
            url=PLATFORM_REPORT_URLS[request.platform.lower()],
            type="external",
            notes=f"Official {request.platform.title()} report page"
        ))

    report_links.append(ReportLink(
        label="Global IFCN Fact Checkers",
        url="https://www.poynter.org/ifcn/",
        type="external",
        notes="International Fact-Checking Network directory"
    ))

    return ReportResponse(
        reportId=report_id,
        summary=summary,
        reportLinks=report_links,
        pibEscalation=pib_links,
    )


@router.get("/report/pib-export")
async def get_pib_export_payload(
    claimText: Optional[str] = Query(None),
    contentUrl: Optional[str] = Query(None)
):
    """
    Get 1-click PIB Fact Check export links (WhatsApp / Email / Portal) for any claim.
    """
    return build_pib_export_payload(claimText, contentUrl)
