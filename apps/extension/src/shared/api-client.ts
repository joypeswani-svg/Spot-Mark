/**
 * api-client.ts — TruthLens Extension: Backend API Client
 *
 * All calls to the FastAPI backend go through this module.
 * API keys are NEVER stored here — they live server-side only.
 *
 * The extension authenticates via a Supabase JWT stored in chrome.storage.local
 * (Step 10). Until then, requests are sent unauthenticated.
 *
 * Resilience strategy:
 *   1. Ping the backend; if offline, return a clearly-labeled local stub
 *   2. On any API error, return "unverified" — NEVER a false positive/negative
 *   3. Callers should check result._isLocalFallback to show the offline indicator
 */

import type {
  AnalyzeTextRequest,
  AnalyzeTextResponse,
  MediaAnalysisResult,
  ReportRequest,
  ReportResponse,
  BlockRequest,
  TrendingFlag,
} from "@truthlens/types";

// ── Config ────────────────────────────────────────────────────────────────────

/**
 * Backend base URL.
 * Development: local Docker / uvicorn on port 8000.
 * Production (Step 10): deployed backend URL set at build time.
 */
const IS_DEV =
  typeof process !== "undefined" && process.env?.NODE_ENV === "development";

let ACTIVE_BACKEND_URL = "http://127.0.0.1:8000";

/** How long to wait before giving up on a backend call (ms). */
const REQUEST_TIMEOUT_MS = 60_000;
/** Ping timeout — fast offline decision. */
const PING_TIMEOUT_MS = 3_000;

// ── Backend reachability cache ────────────────────────────────────────────────

let _backendOnline: boolean | null = null;
let _lastPingAt = 0;
const PING_CACHE_TTL_MS = 10_000; // re-ping at most every 10 s

async function isBackendOnline(): Promise<boolean> {
  const now = Date.now();
  if (_backendOnline !== null && now - _lastPingAt < PING_CACHE_TTL_MS) {
    return _backendOnline;
  }

  // Try 8000 first (default uvicorn port), fallback to 8010
  const urlsToTry = [
    "http://127.0.0.1:8000/api/ping",
    "http://localhost:8000/api/ping",
    "http://127.0.0.1:8000/health",
    "http://localhost:8000/health",
    "http://127.0.0.1:8010/api/ping",
    "http://localhost:8010/api/ping",
  ];

  for (const url of urlsToTry) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), PING_TIMEOUT_MS);
      const res = await fetch(url, { signal: controller.signal });
      clearTimeout(timer);
      if (res.status === 204 || res.status === 200) {
        _backendOnline = true;
        _lastPingAt = now;
        const parsed = new URL(url);
        ACTIVE_BACKEND_URL = parsed.origin;
        console.log(`[TruthLens API] Backend ✓ online (${url}) -> active URL: ${ACTIVE_BACKEND_URL}`);
        return true;
      }
    } catch {
      // try next URL
    }
  }

  _backendOnline = false;
  _lastPingAt = now;
  console.log(`[TruthLens API] Backend ✗ offline`);
  return false;
}

/** Invalidate the cached ping result (e.g., after a known network change). */
export function invalidatePingCache(): void {
  _backendOnline = null;
  _lastPingAt = 0;
}

// ── Auth Token Helper ─────────────────────────────────────────────────────────

async function getAuthToken(): Promise<string | null> {
  return new Promise((resolve) => {
    chrome.storage.local.get(["authToken"], (result) => {
      resolve(result.authToken ?? null);
    });
  });
}

// ── Base Fetch Wrapper ────────────────────────────────────────────────────────

interface FetchOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
}

async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const token = await getAuthToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-TruthLens-Client": "extension/0.2.0",
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${ACTIVE_BACKEND_URL}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => "unknown error");
      throw new Error(`TruthLens API ${response.status}: ${errorText}`);
    }

    return response.json() as Promise<T>;
  } finally {
    clearTimeout(timer);
  }
}

// ── Local Fallback (shown when backend is offline) ────────────────────────────

/**
 * Returns a clearly-labeled "backend offline" stub response.
 * The `_isLocalFallback: true` field tells the popup to show the offline indicator.
 * IMPORTANT: never a false positive or negative — always "unverified".
 */
function _offlineFallback(url?: string): AnalyzeTextResponse & { _isLocalFallback: true } {
  return {
    jobId: `offline-${Date.now()}`,
    resultType: "fast",
    credibility: {
      score: 50,
      band: "unverified",
      color: "gray",
      explanation:
        "TruthLens backend is not reachable. " +
        "This is not a verdict — start the backend to enable analysis.",
      breakdown: {
        claimVerification: 0,
        domainReputation: 0,
        styleClassifier: 0,
        crossCorroboration: 0,
      },
    },
    claims: [],
    domainReputation: undefined,
    deepCheckPending: false,
    analyzedAt: new Date().toISOString(),
    cached: false,
    _isLocalFallback: true,
  };
}

// ── API Methods ───────────────────────────────────────────────────────────────

/**
 * Analyze article text for misinformation.
 * Automatically falls back to the offline stub if the backend is unreachable.
 */
export async function analyzeText(
  request: AnalyzeTextRequest
): Promise<AnalyzeTextResponse & { _isLocalFallback?: boolean }> {
  console.log("[TruthLens API] analyzeText →", request.url ?? "(no URL)", `(${request.text.length} chars)`);

  // Try live backend call directly
  try {
    const result = await apiFetch<AnalyzeTextResponse>("/api/analyze-text", {
      method: "POST",
      body: request,
    });
    _backendOnline = true;
    _lastPingAt = Date.now();
    console.log("[TruthLens API] analyzeText ← score:", result.credibility.score, result.credibility.band);
    return { ...result, _isLocalFallback: false };
  } catch (err) {
    console.warn("[TruthLens API] Direct analyzeText call failed:", err, "— trying fallback ping...");
  }

  // Fast offline check
  const online = await isBackendOnline();
  if (!online) {
    console.warn("[TruthLens API] Backend offline — returning fallback.");
    return _offlineFallback(request.url);
  }

  try {
    const result = await apiFetch<AnalyzeTextResponse>("/api/analyze-text", {
      method: "POST",
      body: request,
    });
    console.log("[TruthLens API] analyzeText ← score:", result.credibility.score, result.credibility.band);
    return { ...result, _isLocalFallback: false };
  } catch (err) {
    _backendOnline = false;
    console.error("[TruthLens API] analyzeText failed:", err);
    return _offlineFallback(request.url);
  }
}

/**
 * Poll for a pending deep-check result.
 */
export async function getAnalysisStatus(
  jobId: string
): Promise<AnalyzeTextResponse> {
  return apiFetch<AnalyzeTextResponse>(`/api/analyze-text/status/${jobId}`);
}

/** Step 8: Analyze an image for AI-generation indicators. */
export async function analyzeImage(formData: FormData): Promise<MediaAnalysisResult> {
  const token = await getAuthToken();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${ACTIVE_BACKEND_URL}/api/analyze-image`, {
      method: "POST",
      headers: {
        "X-TruthLens-Client": "extension/0.2.0",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: formData,
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`Image analysis failed: ${response.status}`);
    return response.json();
  } finally {
    clearTimeout(timer);
  }
}

/** Step 9: Deepfake video detection (async Celery job). */
export async function analyzeVideo(
  videoUrl: string
): Promise<MediaAnalysisResult> {
  return apiFetch<MediaAnalysisResult>("/api/analyze-video", {
    method: "POST",
    body: { url: videoUrl },
  });
}

/** Step 6: Generate a report summary + platform deep-links. */
export async function generateReport(
  request: ReportRequest
): Promise<ReportResponse> {
  return apiFetch<ReportResponse>("/api/report", { method: "POST", body: request });
}

/** Step 6: Add a domain/account to the user's personal block list. */
export async function addBlock(
  request: BlockRequest
): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>("/api/block", { method: "POST", body: request });
}

/** Step 11: Fetch the trending misinformation feed. */
export async function getTrendingFlags(): Promise<TrendingFlag[]> {
  return apiFetch<TrendingFlag[]>("/api/trending-flags");
}

/** Check if the backend is currently reachable (exposed for popup status indicator). */
export { isBackendOnline };
