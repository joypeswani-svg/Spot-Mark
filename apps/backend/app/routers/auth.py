"""routers/auth.py — /api/auth/* — Authentication endpoints (Supabase-backed)"""
from fastapi import APIRouter
router = APIRouter()

@router.post("/verify")
async def verify_token(token: dict):
    """Step 10: Verify Supabase JWT and return user profile. Stub for now."""
    return {"ok": True, "user": None, "note": "Auth coming in Step 10."}

@router.post("/sync")
async def sync_user_data(data: dict):
    """Step 10: Sync block list + truth score between devices."""
    return {"ok": True, "note": "Sync coming in Step 10."}
