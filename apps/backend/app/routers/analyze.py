"""
routers/analyze.py — TruthLens Analysis Endpoints

POST /api/analyze-text                  → claim extraction + verification + score
POST /api/analyze-image                 → AI-generated image detection
POST /api/analyze-video                 → deepfake video detection (async Celery job)
POST /api/analyze-audio                 → voice clone detection (async Celery job)
GET  /api/analyze-text/status/{job_id} → poll for async deep-check results
GET  /api/ping                          → fast liveness check for the extension

Step 3: Real LLM claim extraction + Fact Check Tools API + GDELT + pgvector similarity pipeline.
"""

import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Response
from pydantic import BaseModel, Field

from app.services.synthesizer import analyze_and_synthesize_text

router = APIRouter()


# ── Request / Response Models ────────────────────────────────────────────────

class AnalyzeTextRequest(BaseModel):
    text: str = Field(..., min_length=10, description="Extracted article text")
    url: Optional[str] = Field(None, description="Source URL for domain lookup")
    title: Optional[str] = Field(None, description="Page title")
    language: Optional[str] = Field("en", description="ISO 639-1 language code")


class ScoreBreakdown(BaseModel):
    claimVerification:   float
    domainReputation:    float
    styleClassifier:     float
    crossCorroboration:  float


class CredibilityScore(BaseModel):
    score:       int
    band:        str   # "verified" | "caution" | "likely-false" | "unverified"
    color:       str   # "green" | "yellow" | "red" | "gray"
    explanation: str
    breakdown:   ScoreBreakdown


class Source(BaseModel):
    title:             str
    url:               str
    publisher:         str
    publishedAt:       Optional[str] = None
    summary:           str
    sourceCredibility: Optional[str] = None


class Claim(BaseModel):
    id:           str
    originalText: str
    claim:        str
    verdict:      str    # "TRUE" | "FALSE" | "MISLEADING" | "UNVERIFIED"
    confidence:   float
    explanation:  str
    sources:      list[Source] = []
    textOffset:   Optional[dict] = None


class DomainReputation(BaseModel):
    domain:          str
    biasLean:        str   # "left" | "center" | "right" | …
    factualityRating: str  # "high" | "mostly-factual" | "mixed" | …
    ownershipType:   str   # "corporate" | "independent" | "state-media" | …
    ownerName:       Optional[str] = None
    isSatire:        bool
    notes:           Optional[str] = None


class AnalyzeTextResponse(BaseModel):
    jobId:            str
    resultType:       str    # "fast" | "deep"
    credibility:      CredibilityScore
    claims:           list[Claim]
    domainReputation: Optional[DomainReputation] = None
    deepCheckPending: bool
    analyzedAt:       str
    cached:           bool
    _backendNote:     str = "real-pipeline-v3"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _extract_domain(url: Optional[str]) -> str:
    if not url:
        return "unknown"
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc or "unknown"
    except Exception:
        return "unknown"


# ── GET /api/ping ─────────────────────────────────────────────────────────────

@router.get("/ping", tags=["Health"])
async def ping():
    """
    Ultra-fast liveness check used by the extension to detect if the backend
    is reachable before attempting a full analysis call.
    Returns 204 No Content on success.
    """
    return Response(status_code=204)


# ── POST /api/analyze-text ────────────────────────────────────────────────────

@router.post(
    "/analyze-text",
    response_model=AnalyzeTextResponse,
    summary="Analyze article text for misinformation",
    response_description="Credibility score, claims, and domain reputation",
)
async def analyze_text(
    request: AnalyzeTextRequest,
    background_tasks: BackgroundTasks,
    response: Response,
):
    """
    Analyze article text for misinformation.

    **Step 3 Pipeline**:
    1. Extract atomic factual claims via Gemini API / Ollama / Heuristics
    2. Query Google Fact Check Tools API for professional fact-checker matches
    3. Query GDELT Project API for global news corroboration
    4. Perform pgvector similarity search against curated fact-check database
    5. Synthesize per-claim verdict & weighted composite credibility score
    """
    domain = _extract_domain(request.url)
    job_id = str(uuid.uuid4())

    print(
        f"[TruthLens Step 3] analyze-text <- url={request.url or '(none)'} "
        f"chars={len(request.text)} words={len(request.text.split())}"
    )

    # Execute Step 3 detection & synthesis pipeline
    try:
        pipeline_result = await analyze_and_synthesize_text(
            text=request.text,
            url=request.url,
            title=request.title
        )

        domain_info = pipeline_result.get("domainReputation")
        if domain_info:
            domain_rep = DomainReputation(
                domain=domain_info.get("domain", domain),
                biasLean=domain_info.get("bias", "center"),
                factualityRating=domain_info.get("factuality", "mostly-factual"),
                ownershipType=domain_info.get("ownership", "corporate"),
                ownerName=None,
                isSatire=domain_info.get("isSatire", False),
                notes=domain_info.get("notes", ""),
            )
        else:
            domain_rep = DomainReputation(
                domain=domain,
                biasLean="center",
                factualityRating="mostly-factual",
                ownershipType="corporate",
                ownerName=None,
                isSatire=False,
                notes="Domain reputation lookup.",
            )

        res = AnalyzeTextResponse(
            jobId=job_id,
            resultType="deep",
            credibility=CredibilityScore(**pipeline_result["credibility"]),
            claims=[Claim(**c) for c in pipeline_result["claims"]],
            domainReputation=domain_rep,
            deepCheckPending=False,
            analyzedAt=_now_iso(),
            cached=False,
            _backendNote="real-pipeline-v3",
        )
    except Exception as e:
        # Pipeline crashed (e.g. Gemini quota exhausted, DB down, etc.)
        # Return a degraded but valid response so the extension doesn't show "backend offline"
        import traceback
        traceback.print_exc()
        print(f"[TruthLens] Pipeline error (returning degraded response): {e}")

        # Try to compute at least domain reputation + style scores
        try:
            from app.services.domain_reputation import lookup_domain
            from app.services.style_classifier import classify_writing_style
            from app.services.scorer import calculate_composite_score

            domain_info = lookup_domain(request.url) if request.url else None
            d_score = domain_info["credibilityScore"] if domain_info else 60.0
            style_result = classify_writing_style(request.text)
            s_score = float(style_result["score"])

            credibility = calculate_composite_score(
                claim_verdict_scores=[],
                domain_rep_score=d_score,
                style_classifier_score=s_score,
                corroboration_ratio=0.0
            )

            domain_rep = DomainReputation(
                domain=domain_info.get("domain", domain) if domain_info else domain,
                biasLean=domain_info.get("bias", "center") if domain_info else "center",
                factualityRating=domain_info.get("factuality", "mostly-factual") if domain_info else "mostly-factual",
                ownershipType=domain_info.get("ownership", "corporate") if domain_info else "corporate",
                ownerName=None,
                isSatire=domain_info.get("isSatire", False) if domain_info else False,
                notes="Analysis partially degraded — LLM claims unavailable.",
            )
        except Exception:
            credibility = {
                "score": 50,
                "band": "caution",
                "color": "yellow",
                "explanation": "Analysis partially degraded — some services are temporarily unavailable.",
                "breakdown": {
                    "claimVerification": 0,
                    "domainReputation": 0,
                    "styleClassifier": 0,
                    "crossCorroboration": 0,
                },
            }
            domain_rep = DomainReputation(
                domain=domain,
                biasLean="center",
                factualityRating="mostly-factual",
                ownershipType="corporate",
                ownerName=None,
                isSatire=False,
                notes="Analysis degraded.",
            )

        res = AnalyzeTextResponse(
            jobId=job_id,
            resultType="deep",
            credibility=CredibilityScore(**credibility),
            claims=[],
            domainReputation=domain_rep,
            deepCheckPending=False,
            analyzedAt=_now_iso(),
            cached=False,
            _backendNote="degraded-pipeline-error",
        )

    response.headers["X-TruthLens-Job-Id"] = job_id
    response.headers["X-TruthLens-Cached"] = "false"

    return res


# ── GET /api/analyze-text/status/{job_id} ─────────────────────────────────────

@router.get(
    "/analyze-text/status/{job_id}",
    response_model=AnalyzeTextResponse,
    summary="Poll for deep-check result",
)
async def get_analysis_status(job_id: str):
    """
    Poll for the deep-check result of an async analysis job.
    """
    raise HTTPException(
        status_code=404,
        detail={
            "error": "job_not_found",
            "jobId": job_id,
            "message": "Async deep-check polling not required in sync pipeline.",
        },
    )



# ── POST /api/analyze-image ───────────────────────────────────────────────────

@router.post(
    "/analyze-image",
    summary="Detect AI-generated images",
)
async def analyze_image(file: UploadFile = File(...)):
    """Detect AI-generated images (Step 8)."""
    return {
        "jobId":            str(uuid.uuid4()),
        "mediaType":        "image",
        "manipulationScore": 0,
        "isFlagged":        False,
        "provider":         "local-stub",
        "confidenceRange":  "N/A (Step 8)",
        "explanation":      "AI-image detection not yet implemented (Step 8).",
        "metadataFindings": [],
        "analyzedAt":       _now_iso(),
    }


# ── POST /api/analyze-video ───────────────────────────────────────────────────

class VideoAnalysisRequest(BaseModel):
    url: str = Field(..., description="URL of the video to analyze")


@router.post(
    "/analyze-video",
    summary="Detect deepfake video",
)
async def analyze_video(request: VideoAnalysisRequest):
    """Deepfake video detection via pluggable adapter (Step 9)."""
    return {
        "jobId":            str(uuid.uuid4()),
        "mediaType":        "video",
        "manipulationScore": 0,
        "isFlagged":        False,
        "provider":         "local-stub",
        "confidenceRange":  "N/A (Step 9)",
        "explanation":      "Deepfake video analysis not yet implemented (Step 9).",
        "analyzedAt":       _now_iso(),
    }


# ── POST /api/analyze-audio ───────────────────────────────────────────────────

@router.post(
    "/analyze-audio",
    summary="Detect voice-cloned / AI-generated audio",
)
async def analyze_audio(file: UploadFile = File(...)):
    """Voice clone / AI-generated audio detection (Step 9)."""
    return {
        "jobId":            str(uuid.uuid4()),
        "mediaType":        "audio",
        "manipulationScore": 0,
        "isFlagged":        False,
        "provider":         "local-stub",
        "confidenceRange":  "N/A (Step 9)",
        "explanation":      "Audio clone detection not yet implemented (Step 9).",
        "analyzedAt":       _now_iso(),
    }
