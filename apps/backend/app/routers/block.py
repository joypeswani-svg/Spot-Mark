"""
routers/block.py — Domain & Source Blocking API (Personal Preference Shield)

Endpoints:
- POST /api/block: Add or remove a domain/source from user's personal blocklist
- GET /api/block: Retrieve active user blocklist
"""

from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()

# In-memory blocklists: user_id -> [blocked_domains]
_user_blocklists: Dict[str, List[str]] = {}


class BlockRequest(BaseModel):
    target: str
    targetType: str = "domain"  # "domain" | "account" | "channel"
    action: str = "block"       # "block" | "unblock"
    userId: Optional[str] = "default_user"


class BlockResponse(BaseModel):
    ok: bool
    blocked: str
    action: str
    targetType: str
    blockedDomains: List[str]
    message: str


@router.post("/block", response_model=BlockResponse)
async def toggle_block(request: BlockRequest):
    """
    Add or remove a domain from the user's personal TruthLens block list.
    Affects local browsing/feed rendering only — never sends data to third-party platforms.
    """
    user_id = request.userId or "default_user"
    domain = request.target.strip().lower().replace("www.", "")

    if not domain:
        raise HTTPException(status_code=400, detail="Invalid target domain provided")

    user_list = _user_blocklists.setdefault(user_id, [])

    if request.action == "block":
        if domain not in user_list:
            user_list.append(domain)
        msg = f"Domain {domain} added to your personal blocklist."
    elif request.action == "unblock":
        if domain in user_list:
            user_list.remove(domain)
        msg = f"Domain {domain} removed from your personal blocklist."
    else:
        raise HTTPException(status_code=400, detail="Action must be 'block' or 'unblock'")

    return BlockResponse(
        ok=True,
        blocked=domain,
        action=request.action,
        targetType=request.targetType,
        blockedDomains=user_list,
        message=msg,
    )


@router.get("/block")
async def get_user_blocklist(userId: str = Query("default_user")):
    """
    Retrieve current personal domain blocklist.
    """
    return {
        "userId": userId,
        "blockedDomains": _user_blocklists.get(userId, []),
    }
