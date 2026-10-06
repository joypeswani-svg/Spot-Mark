"""routers/trending.py — GET /api/trending-flags"""
from fastapi import APIRouter
router = APIRouter()

@router.get("/trending-flags")
async def get_trending_flags():
    """Step 11: Real trending feed from DB. Stub for now."""
    return []
