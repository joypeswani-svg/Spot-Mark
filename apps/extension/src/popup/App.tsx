/**
 * App.tsx — TruthLens Extension Popup
 *
 * The main React component rendered in the 380px popup window.
 *
 * Step 2: Reads cached analysis from storage (persisted by the service worker).
 *         Falls back to fresh extraction + backend call if no cached result.
 *         Shows offline indicator when backend is unreachable.
 *         Adds re-analyze button and domain reputation card.
 *
 * Design principles:
 *   - Never shows a bare number — always score + band + explanation
 *   - Report and Block are always two separate, distinct buttons
 *   - Shows "couldn't verify" gracefully on API failure — never a false verdict
 *   - Always shows confidence, never claims 100% certainty
 */

import React, { useEffect, useState, useCallback } from "react";
import type { AnalyzeTextResponse, Claim, DomainReputation as DomainReputationType } from "@truthlens/types";
import { analyzeText, invalidatePingCache } from "../shared/api-client";

// ── Sub-components ────────────────────────────────────────────────────────────

/** Animated SVG score ring */
function ScoreRing({ score, color }: { score: number | null; color: string }) {
  const R = 35; // radius
  const circumference = 2 * Math.PI * R;
  const dashOffset = score !== null
    ? circumference * (1 - score / 100)
    : circumference;

  return (
    <div className="score-ring-container">
      <svg className="score-ring-svg" viewBox="0 0 88 88">
        <circle className="score-ring-bg" cx="44" cy="44" r={R} />
        <circle
          className="score-ring-fill"
          cx="44" cy="44" r={R}
          stroke={color}
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
        />
      </svg>
      <div className="score-ring-label">
        {score !== null ? (
          <>
            <span className="score-number" style={{ color }}>{score}</span>
            <span className="score-unit">/ 100</span>
          </>
        ) : (
          <span className="score-unit" style={{ fontSize: 11 }}>…</span>
        )}
      </div>
    </div>
  );
}

/** A single extracted claim card */
function ClaimCard({ claim }: { claim: Claim }) {
  const colorMap: Record<string, string> = {
    TRUE:       "#22C55E",
    FALSE:      "#EF4444",
    MISLEADING: "#EAB308",
    UNVERIFIED: "#9CA3AF",
  };
  const fillColor = colorMap[claim.verdict] ?? "#9CA3AF";

  return (
    <div className="claim-card">
      <div className="claim-header">
        <span className={`verdict-pill verdict-pill--${claim.verdict}`}>
          {claim.verdict}
        </span>
        <span className="claim-text">{claim.claim}</span>
      </div>
      <p className="claim-explanation">{claim.explanation}</p>
      {/* Confidence bar */}
      <div className="confidence-bar-track">
        <div
          className="confidence-bar-fill"
          style={{ width: `${claim.confidence}%`, background: fillColor }}
        />
      </div>
    </div>
  );
}

/** Domain reputation card */
function DomainReputationCard({ rep }: { rep: DomainReputationType }) {
  const biasLabels: Record<string, string> = {
    "far-left": "Far Left",
    "left": "Left",
    "center-left": "Center-Left",
    "center": "Center",
    "center-right": "Center-Right",
    "right": "Right",
    "far-right": "Far Right",
    "unknown": "Unknown",
  };

  const factualLabels: Record<string, { label: string; color: string }> = {
    "very-high":       { label: "Very High",       color: "#22C55E" },
    "high":            { label: "High",            color: "#22C55E" },
    "mostly-factual":  { label: "Mostly Factual",  color: "#86EFAC" },
    "mixed":           { label: "Mixed",           color: "#EAB308" },
    "low":             { label: "Low",             color: "#EF4444" },
    "very-low":        { label: "Very Low",        color: "#EF4444" },
    "satire":          { label: "Satire/Parody",   color: "#6366F1" },
    "unknown":         { label: "Unknown",         color: "#9CA3AF" },
  };

  const factual = factualLabels[rep.factualityRating] ?? { label: rep.factualityRating, color: "#9CA3AF" };

  return (
    <div className="claims-section" style={{ paddingBottom: 4 }}>
      <div className="section-label">Domain Reputation</div>
      <div className="claim-card" style={{ marginBottom: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
          {rep.domain}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 12px", fontSize: 11 }}>
          <div style={{ color: "var(--text-muted)" }}>Factuality</div>
          <div style={{ color: factual.color, fontWeight: 600 }}>{factual.label}</div>

          <div style={{ color: "var(--text-muted)" }}>Bias Lean</div>
          <div style={{ color: "var(--text-secondary)" }}>{biasLabels[rep.biasLean] ?? rep.biasLean}</div>

          <div style={{ color: "var(--text-muted)" }}>Ownership</div>
          <div style={{ color: "var(--text-secondary)", textTransform: "capitalize" }}>{rep.ownershipType}</div>

          {rep.isSatire && (
            <>
              <div style={{ color: "var(--text-muted)" }}>Type</div>
              <div style={{ color: "#6366F1", fontWeight: 600 }}>Satire / Parody</div>
            </>
          )}
        </div>
        {rep.notes && (
          <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 6, fontStyle: "italic" }}>
            {rep.notes}
          </div>
        )}
      </div>
    </div>
  );
}

/** Loading skeleton */
function LoadingSkeleton() {
  return (
    <div style={{ padding: "20px 16px" }}>
      <div className="score-section" style={{ background: "transparent", padding: 0, marginBottom: 16 }}>
        <div className="skeleton skeleton-score" />
        <div style={{ flex: 1 }}>
          <div className="skeleton skeleton-text" style={{ width: "70%" }} />
          <div className="skeleton skeleton-text" style={{ width: "90%" }} />
          <div className="skeleton skeleton-text-sm" />
        </div>
      </div>
      <div className="skeleton skeleton-text" style={{ width: "40%", marginBottom: 12 }} />
      {[1, 2].map((i) => (
        <div key={i} className="claim-card" style={{ marginBottom: 8 }}>
          <div className="skeleton skeleton-text" style={{ width: "80%" }} />
          <div className="skeleton skeleton-text" style={{ width: "60%" }} />
        </div>
      ))}
    </div>
  );
}

/** Offline indicator banner */
function OfflineBanner() {
  return (
    <div style={{
      margin: "0 16px 8px",
      padding: "6px 12px",
      background: "rgba(99, 102, 241, 0.08)",
      border: "1px solid rgba(99, 102, 241, 0.25)",
      borderRadius: 6,
      fontSize: 11,
      color: "#A5B4FC",
      display: "flex",
      alignItems: "center",
      gap: 6,
    }}>
      <span style={{ fontSize: 14 }}>📡</span>
      <span>Backend offline — showing cached or placeholder data. Start the backend for real analysis.</span>
    </div>
  );
}

// ── Color/Label Maps ──────────────────────────────────────────────────────────

const BAND_LABELS: Record<string, string> = {
  verified:     "✓ Verified",
  caution:      "⚠ Caution",
  "likely-false": "✕ Likely False",
  unverified:   "? Unverified",
};

const COLOR_HEX: Record<string, string> = {
  green:  "#22C55E",
  yellow: "#EAB308",
  red:    "#EF4444",
  gray:   "#9CA3AF",
};

// ── Main App ─────────────────────────────────────────────────────────────────

type AppState =
  | { phase: "loading" }
  | { phase: "not-article"; title: string }
  | { phase: "analyzing"; title: string; url: string; wordCount: number }
  | { phase: "result"; title: string; url: string; result: AnalyzeTextResponse & { _isLocalFallback?: boolean } }
  | { phase: "error"; message: string };

export default function App() {
  const [state, setState] = useState<AppState>({ phase: "loading" });

  // ── Get current tab info and trigger analysis ─────────────────────────────
  const run = useCallback(async () => {
    // Always start with fresh connectivity check (don't inherit stale service worker cache)
    invalidatePingCache();

    // 1. Get active tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id || !tab.url) {
      setState({ phase: "error", message: "No active tab found." });
      return;
    }

    // Skip extension pages
    if (tab.url.startsWith("chrome://") || tab.url.startsWith("chrome-extension://")) {
      setState({ phase: "not-article", title: tab.title ?? "Browser page" });
      return;
    }

    // 2. Check storage for cached analysis result (persisted by service worker)
    const cachedState = await new Promise<any>((resolve) => {
      chrome.storage.local.get([`pageState_${tab.id}`], (result) => {
        resolve(result[`pageState_${tab.id}`] ?? null);
      });
    });

    if (cachedState?.analysis) {
      if (!cachedState.analysis._isLocalFallback) {
        setState({
          phase: "result",
          title: tab.title ?? "",
          url: cachedState.url ?? tab.url,
          result: cachedState.analysis,
        });
        return;
      } else {
        // Stale offline fallback detected — clear from storage and make fresh call
        console.log("[TruthLens Popup] Stale offline fallback detected, clearing & re-analyzing live...");
        invalidatePingCache();
        cachedState.analysis = null;
        // Also clear the stale result in chrome.storage so pollForResult doesn't re-read it
        const clearedState = { ...cachedState, analysis: null, pendingJobId: null };
        await chrome.storage.local.set({ [`pageState_${tab.id}`]: clearedState });

        // If we have extracted text from the service worker, call backend directly
        if (cachedState.extractedText) {
          const wordCount = cachedState.extractedText.split(/\s+/).filter(Boolean).length;
          setState({
            phase: "analyzing",
            title: tab.title ?? "",
            url: cachedState.url ?? tab.url,
            wordCount,
          });

          try {
            const result = await analyzeText({
              text: cachedState.extractedText,
              url: cachedState.url ?? tab.url,
              title: tab.title ?? "",
            });
            setState({ phase: "result", title: tab.title ?? "", url: cachedState.url ?? tab.url, result });
          } catch (err) {
            setState({
              phase: "error",
              message: err instanceof Error ? err.message : "Analysis failed. Please try again.",
            });
          }
          return;
        }
      }
    }

    // 3. If service worker is still analyzing (has extractedText but no analysis), show "analyzing"
    if (cachedState?.extractedText && !cachedState.analysis) {
      const wordCount = cachedState.extractedText.split(/\s+/).filter(Boolean).length;
      setState({
        phase: "analyzing",
        title: tab.title ?? "",
        url: cachedState.url ?? tab.url,
        wordCount,
      });

      // Poll for the result to appear in storage
      pollForResult(tab.id!, tab.title ?? "", cachedState.url ?? tab.url);
      return;
    }

    // 4. No cached state — request extraction from the content script
    let extracted: {
      text: string; title: string; url: string;
      wordCount: number; isArticle: boolean;
    } | null = null;

    try {
      extracted = await chrome.tabs.sendMessage(tab.id, { type: "REQUEST_EXTRACTION" });
    } catch {
      // Content script not attached yet — dynamically inject content script into tab
      try {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ["content/extractor.js", "content/highlighter.js"],
        });
        // Retry message after injection
        extracted = await chrome.tabs.sendMessage(tab.id, { type: "REQUEST_EXTRACTION" });
      } catch (injectErr) {
        console.warn("[TruthLens] Content script injection unavailable for this tab:", injectErr);
        setState({ phase: "not-article", title: tab.title ?? "This page" });
        return;
      }
    }

    if (!extracted || !extracted.isArticle || extracted.wordCount < 100) {
      setState({ phase: "not-article", title: extracted?.title ?? tab.title ?? "This page" });
      return;
    }

    setState({
      phase: "analyzing",
      title: extracted.title,
      url: extracted.url,
      wordCount: extracted.wordCount,
    });

    // 5. Call the backend
    try {
      const result = await analyzeText({
        text: extracted.text,
        url: extracted.url,
        title: extracted.title,
      });

      setState({ phase: "result", title: extracted.title, url: extracted.url, result });
    } catch (err) {
      setState({
        phase: "error",
        message: err instanceof Error ? err.message : "Analysis failed. Please try again.",
      });
    }
  }, []);

  // ── Poll storage for service worker result ────────────────────────────────
  const pollForResult = useCallback((tabId: number, title: string, url: string) => {
    let attempts = 0;
    const maxAttempts = 30; // 30 × 500ms = 15s max wait
    const interval = setInterval(() => {
      attempts++;
      chrome.storage.local.get([`pageState_${tabId}`], (result) => {
        const pageState = result[`pageState_${tabId}`];
        if (pageState?.analysis) {
          clearInterval(interval);
          setState({ phase: "result", title, url, result: pageState.analysis });
        } else if (attempts >= maxAttempts) {
          clearInterval(interval);
          // Don't show error — the service worker may still be working
          // Just re-run the analysis from the popup
          run();
        }
      });
    }, 500);

    // Cleanup on unmount
    return () => clearInterval(interval);
  }, [run]);

  useEffect(() => { run(); }, [run]);

  // ── Force-analyze page regardless of article heuristic ────────────────────
  const forceAnalyze = async () => {
    setState({ phase: "loading" });
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) return;

    try {
      const extracted = await chrome.tabs.sendMessage(tab.id, { type: "REQUEST_EXTRACTION" });
      const textToAnalyze = extracted?.text && extracted.text.trim().length >= 20
        ? extracted.text
        : (tab.title ?? "");

      if (!textToAnalyze || textToAnalyze.trim().length < 10) {
        setState({ phase: "error", message: "Could not find text content on this page." });
        return;
      }

      const wordCount = textToAnalyze.split(/\s+/).filter(Boolean).length;
      setState({
        phase: "analyzing",
        title: extracted?.title || tab.title || "Page Content",
        url: extracted?.url || tab.url || "",
        wordCount,
      });

      const result = await analyzeText({
        text: textToAnalyze,
        url: extracted?.url || tab.url,
        title: extracted?.title || tab.title,
      });

      setState({
        phase: "result",
        title: extracted?.title || tab.title || "Page Content",
        url: extracted?.url || tab.url || "",
        result,
      });
    } catch (err) {
      setState({
        phase: "error",
        message: err instanceof Error ? err.message : "Analysis failed.",
      });
    }
  };

  // ── Re-analyze handler ─────────────────────────────────────────────────────
  const reAnalyze = async () => {
    setState({ phase: "loading" });
    invalidatePingCache();

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) return;

    // Send RE_ANALYZE message to service worker
    chrome.runtime.sendMessage({ type: "RE_ANALYZE", tabId: tab.id }, () => {
      // Wait briefly then start polling for the new result
      setTimeout(() => {
        setState({
          phase: "analyzing",
          title: tab.title ?? "",
          url: tab.url ?? "",
          wordCount: 0,
        });
        pollForResult(tab.id!, tab.title ?? "", tab.url ?? "");
      }, 300);
    });
  };

  // ── Open side panel ───────────────────────────────────────────────────────
  const openSidePanel = async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.id) chrome.sidePanel.open({ tabId: tab.id });
    window.close();
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="popup-container">
      {/* ── Header ── */}
      <header className="popup-header">
        <div className="popup-logo">
          {/* TruthLens logo mark */}
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="10" stroke="#6366F1" strokeWidth="2"/>
            <path d="M8 12l2.5 2.5L16 9" stroke="#22C55E" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span className="popup-logo-text">SpotMark</span>
        </div>
        <div className="popup-header-actions">
          <button className="icon-btn" title="Open side panel" onClick={openSidePanel}>
            ⊞
          </button>
          <button
            className="icon-btn"
            title="Settings"
            onClick={() => chrome.runtime.openOptionsPage()}
          >
            ⚙
          </button>
        </div>
      </header>

      {/* ── Body states ── */}
      {state.phase === "loading" && <LoadingSkeleton />}

      {state.phase === "not-article" && (
        <div className="non-article-notice" style={{ padding: "20px 16px", textAlign: "center" }}>
          <p style={{ fontSize: 32, marginBottom: 8 }}>🔍</p>
          <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 4 }}>
            "{state.title}"
          </p>
          <p style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 16 }}>
            This looks like a homepage or main news index.
          </p>
          <button
            className="btn btn--primary"
            onClick={forceAnalyze}
            style={{ width: "100%", marginBottom: 12, padding: "10px", fontWeight: 600 }}
          >
            ⚡ Analyze Page Content
          </button>
          <p style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.4 }}>
            Tip: You can also open any specific news article or right-click selected text to <strong>Verify with TruthLens</strong>.
          </p>
        </div>
      )}

      {state.phase === "analyzing" && (
        <>
          <div className="score-section">
            <ScoreRing score={null} color="#6366F1" />
            <div className="score-info">
              <div className="score-band" style={{ color: "#6366F1" }}>Analyzing…</div>
              <div className="score-explanation">
                {state.wordCount > 0
                  ? `Running analysis on ${state.wordCount.toLocaleString()} words…`
                  : "Running analysis…"
                }
              </div>
            </div>
          </div>
          <div className="page-info">
            <div className="page-title">{state.title}</div>
            <div className="page-meta">
              <span>{(() => { try { return new URL(state.url).hostname; } catch { return state.url; } })()}</span>
            </div>
          </div>
          <LoadingSkeleton />
        </>
      )}

      {state.phase === "error" && (
        <>
          <div className="score-section">
            <ScoreRing score={null} color="#9CA3AF" />
            <div className="score-info">
              <div className="score-band" style={{ color: "#9CA3AF" }}>? Couldn't Verify</div>
              <div className="score-explanation">
                The analysis service is temporarily unavailable.
                This is <em>not</em> a verdict — we never show a false result.
              </div>
            </div>
          </div>
          <div className="error-banner">{state.message}</div>
          <div style={{ padding: "8px 16px" }}>
            <button className="btn btn--primary" onClick={reAnalyze} style={{ width: "100%" }}>
              ↻ Try Again
            </button>
          </div>
        </>
      )}

      {state.phase === "result" && (() => {
        const { result, title, url } = state;
        const { credibility, claims } = result;
        const hexColor = COLOR_HEX[credibility.color] ?? "#9CA3AF";
        const bandLabel = BAND_LABELS[credibility.band] ?? credibility.band;
        const hostname = (() => { try { return new URL(url).hostname; } catch { return url; } })();
        const isOffline = !!(result as any)._isLocalFallback;

        return (
          <>
            {/* Offline indicator */}
            {isOffline && <OfflineBanner />}

            {/* Score */}
            <div className="score-section">
              <ScoreRing score={credibility.score} color={hexColor} />
              <div className="score-info">
                <div className="score-band" style={{ color: hexColor }}>{bandLabel}</div>
                <div className="score-explanation">{credibility.explanation}</div>
                {result.deepCheckPending && (
                  <div style={{ fontSize: 10, color: "#6366F1", marginTop: 4 }}>
                    ⟳ Deep check running…
                  </div>
                )}
              </div>
            </div>

            {/* Page info */}
            <div className="page-info">
              <div className="page-title">{title}</div>
              <div className="page-meta">
                <span>{hostname}</span>
                {result.cached && (
                  <>
                    <span className="page-meta-dot">•</span>
                    <span>Cached</span>
                  </>
                )}
                <span className="page-meta-dot">•</span>
                <span>{new Date(result.analyzedAt).toLocaleTimeString()}</span>
              </div>
            </div>

            {/* Score breakdown */}
            <div className="claims-section" style={{ paddingBottom: 4 }}>
              <div className="section-label">Score Breakdown</div>
              {Object.entries(credibility.breakdown).map(([key, val]) => {
                const labelMap: Record<string, string> = {
                  claimVerification: "Claim Verification (50%)",
                  domainReputation:  "Domain Reputation (20%)",
                  styleClassifier:   "Writing Style (15%)",
                  crossCorroboration:"Cross-Corroboration (15%)",
                };
                return (
                  <div key={key} style={{ marginBottom: 6 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 3 }}>
                      <span style={{ color: "var(--text-secondary)" }}>{labelMap[key] ?? key}</span>
                      <span style={{ color: hexColor, fontWeight: 600 }}>{Math.round(val)}</span>
                    </div>
                    <div className="confidence-bar-track">
                      <div className="confidence-bar-fill" style={{ width: `${val}%`, background: hexColor }} />
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Domain Reputation */}
            {result.domainReputation && (
              <DomainReputationCard rep={result.domainReputation} />
            )}

            {/* Claims */}
            {claims.length > 0 && (
              <div className="claims-section">
                <div className="section-label">Claims Checked ({claims.length})</div>
                {claims.map((claim) => (
                  <ClaimCard key={claim.id} claim={claim} />
                ))}
              </div>
            )}

            {/* Action bar — Report and Block are ALWAYS separate */}
            <div className="action-bar">
              <button className="btn btn--secondary" onClick={reAnalyze} title="Re-run analysis">
                ↻ Re-analyze
              </button>
              <button className="btn btn--secondary" onClick={openSidePanel}>
                Full Report
              </button>
              {/* Report = external claim to platform. Block = personal local preference. */}
              <button
                className="btn btn--report"
                title="Report this content to a platform or authority"
                onClick={() => {
                  // Step 6: open report flow in side panel
                  openSidePanel();
                }}
              >
                🚩 Report
              </button>
              <button
                className="btn btn--block"
                title="Block this domain in TruthLens (personal preference only)"
                onClick={() => {
                  // Step 6: open block flow in side panel
                  openSidePanel();
                }}
              >
                🚫 Block
              </button>
            </div>
          </>
        );
      })()}

      {/* Footer */}
      <footer className="popup-footer">
        SpotMark v0.2 · Never 100% certain · Always cite sources
      </footer>
    </div>
  );
}

