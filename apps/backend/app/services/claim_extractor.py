"""
services/claim_extractor.py — LLM Factual Claim Extraction

Decomposes raw article text into atomic factual claims using:
1. Google Gemini API (structured JSON mode via free-tier SDK / HTTP)
2. Local Ollama fallback (Llama 3.1 8B / Mistral 7B) if Gemini API key is missing or rate limited
3. Rule-based heuristic fallback if both LLMs are offline
"""

import json
import re
import logging
import asyncio
from typing import List, Optional, Dict, Any
import httpx

from app.config import settings

logger = logging.getLogger("truthlens.claim_extractor")


class ExtractedClaimItem:
    def __init__(self, claim: str, original_text: str, start_offset: int = 0, end_offset: int = 0):
        self.claim = claim
        self.original_text = original_text
        self.start_offset = start_offset
        self.end_offset = end_offset

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim,
            "originalText": self.original_text,
            "textOffset": {"start": self.start_offset, "end": self.end_offset},
        }


EXTRACTION_PROMPT = """You are a senior factual claim extractor for a fact-checking pipeline.
Analyze the following article text and extract up to 5 main atomic factual claims that can be objectively verified or debunked.

Guidelines:
- A factual claim is an assertion about real-world events, statistics, quotes, historic facts, or scientific statements.
- DO NOT extract opinions, subjective values, speculative predictions, or rhetorical questions.
- Rephrase each claim into a clear, standalone, self-contained statement.
- Identify the exact original sentence from the text that contains the claim.

Return strictly valid JSON format with a key "claims" containing an array of objects matching this schema:
{{
  "claims": [
    {{
      "claim": "Clear standalone statement of the factual claim",
      "originalText": "Exact sentence from article text"
    }}
  ]
}}

Article Text:
\"\"\"{article_text}\"\"\"
"""


async def extract_claims_gemini(text: str) -> Optional[List[ExtractedClaimItem]]:
    """Extract claims using Google Gemini API."""
    if settings.LLM_PROVIDER == "lmstudio":
        return None  # User explicitly configured LM Studio — skip Gemini

    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here":
        logger.info("Gemini API key not configured. Skipping Gemini extraction.")
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = EXTRACTION_PROMPT.format(article_text=text[:3000])

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

        data = json.loads(raw_json)
        items = data.get("claims", [])

        results: List[ExtractedClaimItem] = []
        for item in items:
            c_text = item.get("claim", "").strip()
            o_text = item.get("originalText", "").strip()
            if not c_text:
                continue

            # Find offset in original text
            offset_start = text.find(o_text) if o_text else -1
            offset_end = offset_start + len(o_text) if offset_start != -1 else 0
            offset_start = max(0, offset_start)

            results.append(ExtractedClaimItem(
                claim=c_text,
                original_text=o_text or c_text,
                start_offset=offset_start,
                end_offset=offset_end,
            ))

        return results if results else None
    except Exception as e:
        logger.warning(f"Gemini claim extraction failed: {e}")
        return None


async def extract_claims_groq(text: str) -> Optional[List[ExtractedClaimItem]]:
    """Extract claims using Groq's ultra-fast LPU API (e.g. Llama 3.3 70B)."""
    if not settings.GROQ_API_KEY:
        return None

    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        prompt = EXTRACTION_PROMPT.format(article_text=text[:3500])

        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json={
                "model": settings.GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a senior factual claim extractor. Return strictly valid JSON with key 'claims'."},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
                "max_tokens": 1500,
            })
            if resp.status_code != 200:
                logger.warning(f"Groq claim extraction returned {resp.status_code}: {resp.text[:200]}")
                return None

            data = resp.json()
            raw_content = data["choices"][0]["message"]["content"].strip()
            parsed = json.loads(raw_content)
            items = parsed.get("claims", [])

            results: List[ExtractedClaimItem] = []
            for item in items:
                c_text = item.get("claim", "").strip()
                o_text = item.get("originalText", "").strip()
                if not c_text:
                    continue
                start = text.find(o_text) if o_text else 0
                start = max(0, start)
                end = start + len(o_text) if o_text else 0
                results.append(ExtractedClaimItem(c_text, o_text or c_text, start, end))

            if results:
                logger.info(f"Extracted {len(results)} claims via Groq ({settings.GROQ_MODEL}).")
            return results if results else None
    except Exception as e:
        logger.warning(f"Groq claim extraction failed: {e}")
        return None


async def extract_claims_lmstudio(text: str) -> Optional[List[ExtractedClaimItem]]:
    """Extract claims using LM Studio's OpenAI-compatible API (http://localhost:1234/v1)."""
    base_url = settings.LMSTUDIO_BASE_URL.rstrip('/')
    
    # Ultra-fast 0.3s ping to verify if LM Studio server port is listening
    try:
        async with httpx.AsyncClient(timeout=0.3, trust_env=False) as ping_client:
            p_res = await ping_client.get(f"{base_url}/models")
            if p_res.status_code != 200:
                return None
    except Exception:
        return None

    url = f"{base_url}/chat/completions"
    model_name = settings.LMSTUDIO_MODEL
    prompt = EXTRACTION_PROMPT.format(article_text=text[:2500])

    try:
        async with httpx.AsyncClient(timeout=2.5, trust_env=False) as client:
            logger.info(f"Connecting to LM Studio at {url} using model '{model_name}'...")
            resp = await client.post(url, json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "You are a senior factual claim extractor. Return ONLY valid JSON format with key 'claims'."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 800,
            })
            if resp.status_code != 200:
                logger.warning(f"LM Studio returned HTTP {resp.status_code}: {resp.text[:200]}")
                return None

            data = resp.json()
            raw_content = data["choices"][0]["message"]["content"]

            # Clean reasoning <think>...</think> tags and markdown code blocks
            raw_json = raw_content.strip()
            raw_json = re.sub(r'<think>.*?</think>', '', raw_json, flags=re.DOTALL).strip()
            if raw_json.startswith("```"):
                lines = raw_json.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw_json = "\n".join(lines).strip()

            parsed = json.loads(raw_json)
            items = parsed.get("claims", [])

            results: List[ExtractedClaimItem] = []
            for item in items:
                if isinstance(item, dict):
                    c_text = item.get("claim", "").strip()
                    o_text = item.get("originalText", "").strip()
                elif isinstance(item, str):
                    c_text = item.strip()
                    o_text = item.strip()
                else:
                    continue

                if not c_text:
                    continue

                start = text.find(o_text) if o_text else 0
                start = max(0, start)
                end = start + len(o_text) if o_text else 0
                results.append(ExtractedClaimItem(c_text, o_text or c_text, start, end))
            
            if results:
                logger.info(f"Successfully extracted {len(results)} claims via local LM Studio model ({model_name}).")
                return results
    except Exception as e:
        logger.warning(f"LM Studio claim extraction error: {e}")

    return None


async def extract_claims_ollama(text: str) -> Optional[List[ExtractedClaimItem]]:
    """Fallback: Extract claims using local Ollama instance."""
    try:
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
        prompt = EXTRACTION_PROMPT.format(article_text=text[:2500])
        
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json={
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            })
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            raw_response = data.get("response", "{}")
            parsed = json.loads(raw_response)
            items = parsed.get("claims", [])
            
            results: List[ExtractedClaimItem] = []
            for item in items:
                c_text = item.get("claim", "").strip()
                o_text = item.get("originalText", "").strip()
                if not c_text:
                    continue
                start = text.find(o_text) if o_text else 0
                start = max(0, start)
                end = start + len(o_text) if o_text else 0
                results.append(ExtractedClaimItem(c_text, o_text or c_text, start, end))
            return results if results else None
    except Exception as e:
        logger.debug(f"Ollama claim extraction unavailable: {e}")
        return None


def extract_claims_heuristic(text: str) -> List[ExtractedClaimItem]:
    """
    Offline Rule-based Heuristic Fallback:
    Splits text into sentences, identifies declarative factual statements containing numbers,
    quotes, dates, or key assertions.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    candidate_sentences = []

    # Indicators of factual assertions
    factual_regex = re.compile(
        r'\b(\d+|percent|million|billion|trillion|dollars|announced|reported|found|proved|confirmed|died|killed|discovered|according to|stated)\b',
        re.IGNORECASE
    )

    for s in sentences:
        s_clean = s.strip()
        if 20 <= len(s_clean) <= 250:
            if factual_regex.search(s_clean):
                candidate_sentences.append(s_clean)

    if not candidate_sentences:
        # Fallback to first 3 non-trivial sentences
        candidate_sentences = [s.strip() for s in sentences if len(s.strip()) >= 30][:3]

    results: List[ExtractedClaimItem] = []
    for s in candidate_sentences[:4]:
        start = text.find(s)
        start = max(0, start)
        end = start + len(s)
        results.append(ExtractedClaimItem(
            claim=s,
            original_text=s,
            start_offset=start,
            end_offset=end
        ))

    return results


async def extract_claims(text: str) -> List[ExtractedClaimItem]:
    """
    Main entry point for claim extraction with Dual Cloud API & Local LM Studio Fallback.
    
    Fallback Order:
    1. Groq Cloud API (if GROQ_API_KEY set)
    2. Gemini Cloud API (if GEMINI_API_KEY set)
    3. Local LM Studio Model (http://localhost:1234/v1 - auto-detected)
    4. Local Ollama (http://localhost:11434)
    5. Offline Heuristic Fallback Engine
    """
    # 1. Try Groq Cloud API
    if settings.GROQ_API_KEY:
        try:
            if claims := await extract_claims_groq(text):
                logger.info(f"Extracted {len(claims)} claims via Groq API.")
                return claims
        except Exception as e:
            logger.warning(f"Groq API error/quota exhausted: {e}. Falling back to next provider...")

    # 2. Try Gemini Cloud API
    if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your_gemini_api_key_here":
        try:
            if claims := await extract_claims_gemini(text):
                logger.info(f"Extracted {len(claims)} claims via Gemini API.")
                return claims
        except Exception as e:
            logger.warning(f"Gemini API error/quota exhausted: {e}. Falling back to LM Studio...")
    else:
        logger.info("Cloud API keys missing or unconfigured. Proceeding to Local LM Studio...")

    # 3. Local LM Studio Fallback (http://localhost:1234/v1)
    try:
        if claims := await asyncio.wait_for(extract_claims_lmstudio(text), timeout=1.5):
            return claims
    except Exception:
        logger.info("LM Studio timeout/unavailable (1.5s limit). Moving to heuristics...")

    # 4. Try Ollama Fallback (0.8s timeout)
    try:
        if claims := await asyncio.wait_for(extract_claims_ollama(text), timeout=0.8):
            logger.info(f"Extracted {len(claims)} claims via Ollama fallback.")
            return claims
    except Exception:
        pass

    # 5. Rule-based Heuristic Fallback
    logger.info("Using heuristic claim extraction fallback.")
    return extract_claims_heuristic(text)


