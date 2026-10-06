"""
services/synthesizer.py — Evidence Orchestrator & Claim Verdict Synthesizer

Combines evidence from:
1. Google Fact Check Tools API
2. pgvector similarity search over curated corpus
3. GDELT global news corroboration API

Uses LLM (Gemini/Ollama) or rule-based evidence synthesis to yield structured claim verdicts
(TRUE / FALSE / MISLEADING / UNVERIFIED), confidence ranges, explanations, and cited sources.
"""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
import httpx

from app.config import settings
from app.services.scorer import calculate_composite_score
from app.services.claim_extractor import extract_claims, ExtractedClaimItem
from app.services.fact_checker import search_google_fact_check, FactCheckMatch
from app.services.gdelt_service import query_gdelt_corroboration, GdeltArticle
from app.services.vector_search import search_vector_corpus
from app.services.domain_reputation import lookup_domain, get_domain_score
from app.services.style_classifier import classify_writing_style, get_style_score

logger = logging.getLogger("truthlens.synthesizer")


SYNTHESIS_PROMPT = """You are a senior factual verification synthesizer.
Evaluate the candidate claim against the provided evidence gathered from professional fact-checkers and news sources.

Candidate Claim: "{claim}"

Evidence Gathered:
- Professional Fact Check Matches: {fact_check_matches}
- Vector Corpus Matches: {vector_matches}
- News Corroboration (GDELT): {gdelt_info}

Instructions:
1. Determine the verdict for this claim: "TRUE", "FALSE", "MISLEADING", or "UNVERIFIED".
2. Assign a confidence score between 0 and 100 based on strength of evidence.
3. Write a concise, 1-2 sentence plain-English explanation explaining WHY this verdict was assigned.
4. Select up to 3 most relevant cited sources from the evidence.

Return strictly valid JSON format with this schema:
{{
  "verdict": "TRUE|FALSE|MISLEADING|UNVERIFIED",
  "confidence": 85,
  "explanation": "Clear plain English explanation.",
  "sources": [
    {{
      "title": "Article title",
      "url": "https://...",
      "publisher": "Publisher name",
      "summary": "1-sentence summary of what this source says"
    }}
  ]
}}
"""


async def _llm_synthesize_verdict(
    claim: str,
    fc_matches: List[FactCheckMatch],
    vec_matches: List[Dict[str, Any]],
    gdelt_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Synthesize verdict using Gemini API if key is present."""
    if settings.LLM_PROVIDER == "lmstudio":
        return None  # Skip Gemini when LM Studio is configured

    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here":
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        fc_summary = [m.to_dict() for m in fc_matches]
        gdelt_summary = {
            "count": gdelt_data.get("articleCount", 0),
            "sample": [a.get("title") for a in gdelt_data.get("articles", [])[:3]]
        }

        prompt = SYNTHESIS_PROMPT.format(
            claim=claim,
            fact_check_matches=json.dumps(fc_summary),
            vector_matches=json.dumps(vec_matches),
            gdelt_info=json.dumps(gdelt_summary)
        )

        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            ),
            timeout=10.0,  # Fail fast — don't let Gemini SDK retries hang for 55s+
        )

        raw_json = (response.text or "").strip()
        if raw_json.startswith("```"):
            lines = raw_json.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw_json = "\n".join(lines).strip()

        parsed = json.loads(raw_json)
        return parsed
    except Exception as e:
        logger.warning(f"Gemini LLM synthesis failed: {e}", exc_info=True)
        return None


async def _llm_synthesize_verdict_groq(
    claim: str,
    fc_matches: List[FactCheckMatch],
    vec_matches: List[Dict[str, Any]],
    gdelt_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Synthesize verdict using Groq Llama 3.3 70B API."""
    if not settings.GROQ_API_KEY:
        return None

    try:
        url = "https://api.groq.com/openai/v1/chat/completions"

        fc_summary = [m.to_dict() for m in fc_matches]
        gdelt_summary = {
            "count": gdelt_data.get("articleCount", 0),
            "sample": [a.get("title") for a in gdelt_data.get("articles", [])[:3]]
        }

        prompt = SYNTHESIS_PROMPT.format(
            claim=claim[:1000],
            fact_check_matches=json.dumps(fc_summary),
            vector_matches=json.dumps(vec_matches),
            gdelt_info=json.dumps(gdelt_summary)
        )

        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json={
                "model": settings.GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a senior factual verdict synthesizer. Return strictly valid JSON with keys verdict, confidence, explanation, sources."},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
                "max_tokens": 1000,
            })
            if resp.status_code != 200:
                logger.warning(f"Groq synthesis returned {resp.status_code}: {resp.text[:200]}")
                return None

            data = resp.json()
            raw_content = data["choices"][0]["message"]["content"].strip()
            parsed = json.loads(raw_content)
            logger.info(f"Synthesized verdict via Groq ({settings.GROQ_MODEL}): {parsed.get('verdict')}")
            return parsed
    except Exception as e:
        logger.warning(f"Groq synthesis failed: {e}")
        return None


async def _llm_synthesize_verdict_lmstudio(
    claim: str,
    fc_matches: List[FactCheckMatch],
    vec_matches: List[Dict[str, Any]],
    gdelt_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Synthesize verdict using local LM Studio (e.g. Qwen3 8B)."""
    try:
        url = f"{settings.LMSTUDIO_BASE_URL.rstrip('/')}/chat/completions"

        fc_summary = [m.to_dict() for m in fc_matches]
        gdelt_summary = {
            "count": gdelt_data.get("articleCount", 0),
            "sample": [a.get("title") for a in gdelt_data.get("articles", [])[:3]]
        }

        prompt = SYNTHESIS_PROMPT.format(
            claim=claim[:500],
            fact_check_matches=json.dumps(fc_summary),
            vector_matches=json.dumps(vec_matches),
            gdelt_info=json.dumps(gdelt_summary)
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json={
                "model": settings.LMSTUDIO_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a factual verdict synthesizer. Return strictly valid JSON with no extraneous commentary."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 600,
            })
            if resp.status_code != 200:
                logger.warning(f"LM Studio synthesis returned {resp.status_code}: {resp.text[:200]}")
                return None

            data = resp.json()
            raw_content = data["choices"][0]["message"]["content"]

            import re as _re
            raw_json = _re.sub(r'<think>.*?</think>', '', raw_content.strip(), flags=_re.DOTALL).strip()
            if raw_json.startswith("```"):
                lines = raw_json.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw_json = "\n".join(lines).strip()

            parsed = json.loads(raw_json)
            return parsed
    except Exception as e:
        logger.warning(f"LM Studio synthesis failed: {e}", exc_info=True)
        return None



def _rule_synthesize_verdict(
    claim: str,
    fc_matches: List[FactCheckMatch],
    vec_matches: List[Dict[str, Any]],
    gdelt_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deterministic evidence-based rule synthesizer used when LLM is unavailable.
    """
    sources = []

    # 1. Google Fact Check Match
    if fc_matches:
        top_fc = fc_matches[0]
        rating_lower = top_fc.textual_rating.lower()

        if any(w in rating_lower for w in ["false", "fake", "hoax", "incorrect", "debunked", "false/fake"]):
            verdict = "FALSE"
            confidence = 90
        elif any(w in rating_lower for w in ["true", "correct", "accurate"]):
            verdict = "TRUE"
            confidence = 88
        elif any(w in rating_lower for w in ["misleading", "partly false", "exaggerated", "context"]):
            verdict = "MISLEADING"
            confidence = 80
        else:
            verdict = "UNVERIFIED"
            confidence = 50

        explanation = f"Fact-checked as {top_fc.textual_rating} by {top_fc.publisher}."

        for m in fc_matches[:3]:
            sources.append({
                "title": m.title,
                "url": m.url,
                "publisher": m.publisher,
                "summary": f"Fact-checked as {m.textual_rating}."
            })

        return {
            "verdict": verdict,
            "confidence": confidence,
            "explanation": explanation,
            "sources": sources
        }

    # 2. Vector Search Match (pgvector)
    if vec_matches:
        top_v = vec_matches[0]
        v_verdict = top_v.get("verdict", "UNVERIFIED")
        v_pub = top_v.get("sourceName", "Corpus Match")
        v_exp = top_v.get("explanation", "")

        confidence = int(top_v.get("similarity", 0.7) * 100)
        explanation = f"Matched internal fact-check corpus ({v_pub}): {v_exp}"

        for vm in vec_matches[:2]:
            sources.append({
                "title": f"Corpus match ({vm.get('sourceName')})",
                "url": vm.get("sourceUrl", ""),
                "publisher": vm.get("sourceName", "Fact-Checker"),
                "summary": vm.get("explanation", "")
            })

        return {
            "verdict": v_verdict,
            "confidence": min(95, confidence),
            "explanation": explanation,
            "sources": sources
        }

    # 3. GDELT News Corroboration
    article_count = gdelt_data.get("articleCount", 0)
    domain_count = gdelt_data.get("domainCount", 0)
    gdelt_articles = gdelt_data.get("articles", [])

    if article_count >= 3:
        verdict = "TRUE"
        confidence = min(85, 50 + (domain_count * 7))
        explanation = f"Corroborated by news coverage across {domain_count} independent media outlets."

        for a in gdelt_articles[:3]:
            sources.append({
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "publisher": a.get("domain", "News Outlet"),
                "summary": f"Covered on {a.get('domain', 'news')}"
            })

        return {
            "verdict": verdict,
            "confidence": confidence,
            "explanation": explanation,
            "sources": sources
        }

    # 4. Fallback / Unverified
    return {
        "verdict": "UNVERIFIED",
        "confidence": 40,
        "explanation": "No direct fact-checks or sufficient corroborating news coverage were found for this claim.",
        "sources": []
    }


async def analyze_and_synthesize_text(text: str, url: Optional[str] = None, title: Optional[str] = None) -> Dict[str, Any]:
    """
    Full Analysis Pipeline (Steps 3–5):
    1. Extract claims from text
    2. For each claim: Fact Check API → GDELT → pgvector → Synthesize verdict
    3. Domain reputation lookup (if URL provided)
    4. Writing-style credibility classification
    5. Calculate composite credibility score from all signals
    """
    # ── Step 5a: Domain reputation (runs in <1ms, no I/O) ───────────────────
    domain_info = lookup_domain(url) if url else None
    domain_score = domain_info["credibilityScore"] if domain_info else 60.0
    logger.info(f"Domain reputation: {domain_info['domain'] if domain_info else 'N/A'} → {domain_score}")

    # ── Step 5b: Writing-style classifier (runs in <1ms, regex only) ────────
    style_result = classify_writing_style(text)
    style_score = float(style_result["score"])
    logger.info(f"Style classifier score: {style_score}, findings: {style_result['findings']}")

    # ── Step 1: Extract claims ──────────────────────────────────────────────
    extracted_items = await extract_claims(text)

    claims_output = []
    verdict_scores = []
    corroboration_counts = 0

    lmstudio_online = False
    if not settings.GROQ_API_KEY and (not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here"):
        try:
            async with httpx.AsyncClient(timeout=0.8) as client:
                m_res = await client.get(f"{settings.LMSTUDIO_BASE_URL.rstrip('/')}/models")
                lmstudio_online = (m_res.status_code == 200)
        except Exception:
            lmstudio_online = False

    for idx, item in enumerate(extracted_items[:3]):
        # ── Step 2: Gather Evidence in Parallel ─────────────────────────────
        try:
            fc_matches, vec_matches, gdelt_data = await asyncio.wait_for(
                asyncio.gather(
                    search_google_fact_check(item.claim),
                    search_vector_corpus(item.claim),
                    query_gdelt_corroboration(item.claim),
                    return_exceptions=True
                ),
                timeout=3.0
            )
            fc_matches = fc_matches if isinstance(fc_matches, list) else []
            vec_matches = vec_matches if isinstance(vec_matches, list) else []
            gdelt_data = gdelt_data if isinstance(gdelt_data, dict) else {"articleCount": 0}
        except Exception:
            fc_matches, vec_matches, gdelt_data = [], [], {"articleCount": 0}

        if gdelt_data.get("articleCount", 0) > 0:
            corroboration_counts += 1

        # ── Step 3: Synthesize Verdict ──────────────────────────────────────
        llm_res = None
        if settings.GROQ_API_KEY:
            llm_res = await _llm_synthesize_verdict_groq(item.claim, fc_matches, vec_matches, gdelt_data)

        if not llm_res and settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your_gemini_api_key_here":
            llm_res = await _llm_synthesize_verdict(item.claim, fc_matches, vec_matches, gdelt_data)

        # Fast deterministic evidence synthesizer (0.001s) when local LLM is used
        if not llm_res:
            llm_res = _rule_synthesize_verdict(item.claim, fc_matches, vec_matches, gdelt_data)

        verdict = llm_res.get("verdict", "UNVERIFIED")
        confidence = float(llm_res.get("confidence", 50))
        explanation = llm_res.get("explanation", "")
        sources = llm_res.get("sources", [])

        # Score mapping for composite score: TRUE=100, UNVERIFIED=75, MISLEADING=40, FALSE=0
        score_val = 100 if verdict == "TRUE" else (0 if verdict == "FALSE" else (40 if verdict == "MISLEADING" else 75))
        verdict_scores.append(score_val)

        claims_output.append({
            "id": f"claim-{idx+1}",
            "originalText": item.original_text,
            "claim": item.claim,
            "verdict": verdict,
            "confidence": confidence,
            "explanation": explanation,
            "sources": sources,
            "textOffset": {"start": item.start_offset, "end": item.end_offset}
        })

    # ── Step 4+5: Calculate Composite Credibility Score ─────────────────────
    corroboration_ratio = (corroboration_counts / max(1, len(extracted_items)))
    has_false = any(c["verdict"] == "FALSE" for c in claims_output)
    has_misleading = any(c["verdict"] == "MISLEADING" for c in claims_output)

    credibility = calculate_composite_score(
        claim_verdict_scores=verdict_scores,
        domain_rep_score=domain_score,
        style_classifier_score=style_score,
        corroboration_ratio=corroboration_ratio,
        has_false_claims=has_false,
        has_misleading_claims=has_misleading,
    )

    return {
        "credibility": credibility,
        "claims": claims_output,
        "domainReputation": domain_info,
        "styleAnalysis": {
            "score": style_result["score"],
            "findings": style_result["findings"],
            "details": style_result["details"],
        },
    }
