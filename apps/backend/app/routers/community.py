"""routers/community.py — POST /api/community-note, GET /api/community-note"""
from typing import Optional
from fastapi import APIRouter, Query
router = APIRouter()

@router.post("/community-note")
async def submit_community_note(note: dict):
    """Step 11: Community notes with contributor reputation scoring. Stub for now."""
    return {"ok": True, "note": "Community notes feature coming in Step 11."}

@router.get("/community-note")
async def get_community_notes(url: Optional[str] = Query(None)):
    """Step 11: Fetch community notes for a URL."""
    return []
