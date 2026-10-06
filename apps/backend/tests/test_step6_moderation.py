"""
tests/test_step6_moderation.py — Unit tests for Step 6 Report & Block APIs + PIB Fact Check Escalation
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_report_misinformation_and_pib_escalation():
    response = client.post(
        "/api/report",
        json={
            "contentUrl": "https://suspicious-news-site.in/fake-article",
            "claimText": "Government announced 1000 free smartphones for all citizens",
            "categories": ["false_information", "clickbait"],
            "platform": "whatsapp"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "reportId" in data
    assert "pibEscalation" in data
    pib = data["pibEscalation"]
    
    # Verify PIB Fact Check WhatsApp (+91 8799711259) link
    assert "918799711259" in pib["pibWhatsAppUrl"]
    assert "pibfactcheck%40gmail.com" in pib["pibEmailUrl"] or "pibfactcheck" in pib["pibEmailUrl"]
    assert pib["pibPortalUrl"] == "https://factcheck.pib.gov.in"
    
    # Verify links list contains PIB direct buttons
    links = data["reportLinks"]
    assert any(l["type"] == "pib_whatsapp" for l in links)
    assert any(l["type"] == "pib_email" for l in links)


def test_get_pib_export_payload():
    response = client.get(
        "/api/report/pib-export",
        params={
            "claimText": "Virus vaccine causes magnet attraction",
            "contentUrl": "https://example.com/fake-vaccine"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "wa.me/918799711259" in data["pibWhatsAppUrl"]
    assert "mailto:pibfactcheck@gmail.com" in data["pibEmailUrl"]
    assert "Virus vaccine" in data["formattedText"]


def test_block_domain_toggle():
    # 1. Block domain
    res_block = client.post(
        "/api/block",
        json={
            "target": "infowars.com",
            "targetType": "domain",
            "action": "block",
            "userId": "user_123"
        }
    )
    assert res_block.status_code == 200
    data_block = res_block.json()
    assert data_block["ok"] is True
    assert "infowars.com" in data_block["blockedDomains"]

    # 2. Get active blocklist
    res_get = client.get("/api/block", params={"userId": "user_123"})
    assert res_get.status_code == 200
    assert "infowars.com" in res_get.json()["blockedDomains"]

    # 3. Unblock domain
    res_unblock = client.post(
        "/api/block",
        json={
            "target": "infowars.com",
            "targetType": "domain",
            "action": "unblock",
            "userId": "user_123"
        }
    )
    assert res_unblock.status_code == 200
    assert "infowars.com" not in res_unblock.json()["blockedDomains"]
