/**
 * service-worker.ts — TruthLens Background Service Worker (MV3)
 *
 * Responsibilities:
 *   - Install lifecycle: set up context menus, default storage state
 *   - Tab update lifecycle: clear stale per-tab state on navigation
 *   - Message routing: relay messages between content scripts and popup
 *   - Context menu: "Verify with TruthLens" right-click action
 *   - Backend analysis: call /api/analyze-text after content extraction
 *   - Alarms: poll for pending deep-check job results (Step 3+)
 *   - Badge: update the action badge with credibility color/score
 *
 * Step 2: Extension is now wired to the FastAPI backend.
 *         On extraction → calls analyzeText() → persists result → updates badge.
 */

import type { ExtensionPageState, BlockList, AnalyzeTextResponse } from "@truthlens/types";
import { analyzeText } from "../shared/api-client";

// ── Constants ─────────────────────────────────────────────────────────────────

const CONTEXT_MENU_ID = "truthlens-verify";
const ALARM_POLL = "truthlens-poll-jobs";

// ── Install / Update ─────────────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener((details) => {
  console.log("[TruthLens] Installed/Updated:", details.reason);

  // Register right-click context menu
  chrome.contextMenus.create({
    id: CONTEXT_MENU_ID,
    title: "Verify with TruthLens",
    contexts: ["page", "selection", "image", "video", "link"],
  });

  // Seed default block list in storage if not already set
  chrome.storage.local.get(["blockList"], (result) => {
    if (!result.blockList) {
      const defaultBlockList: BlockList = {
        domains: [],
        accounts: [],
        channels: [],
        updatedAt: new Date().toISOString(),
      };
      chrome.storage.local.set({ blockList: defaultBlockList });
      console.log("[TruthLens] Block list initialized.");
    }
  });

  // Seed user preferences
  chrome.storage.local.get(["preferences"], (result) => {
    if (!result.preferences) {
      chrome.storage.local.set({
        preferences: {
          highlightingEnabled: true,
          notificationsEnabled: false,
          explainLikeImFive: false,
          familyShieldEnabled: false,
          autoAnalyze: true,
        },
      });
    }
  });
});

// ── Tab Navigation — clear stale state ───────────────────────────────────────

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  // Only act when the main frame finishes loading a new URL
  if (changeInfo.status !== "complete" || !tab.url) return;
  if (tab.url.startsWith("chrome://") || tab.url.startsWith("chrome-extension://")) return;

  console.log(`[TruthLens] Tab ${tabId} navigated to:`, tab.url);

  // Clear previous page state for this tab
  chrome.storage.local.remove([`pageState_${tabId}`], () => {
    console.log(`[TruthLens] Cleared stale state for tab ${tabId}`);
  });

  // Reset badge to neutral (gray, no text) while new page loads
  setBadge(tabId, "neutral");
});

chrome.tabs.onRemoved.addListener((tabId) => {
  // Clean up storage for closed tabs
  chrome.storage.local.remove([`pageState_${tabId}`]);
});

// ── Context Menu Handler ──────────────────────────────────────────────────────

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== CONTEXT_MENU_ID || !tab?.id) return;

  console.log("[TruthLens] Context menu triggered:", {
    selectionText: info.selectionText?.slice(0, 100),
    srcUrl: info.srcUrl,
    linkUrl: info.linkUrl,
    pageUrl: info.pageUrl,
  });

  // Open the side panel for the analysis result
  chrome.sidePanel.open({ tabId: tab.id });

  // Send a message to the content script to trigger extraction
  // (content script handles what to extract based on context)
  chrome.tabs.sendMessage(tab.id, {
    type: "CONTEXT_MENU_VERIFY",
    payload: {
      selectionText: info.selectionText ?? null,
      srcUrl: info.srcUrl ?? null,
      linkUrl: info.linkUrl ?? null,
      pageUrl: info.pageUrl,
    },
  });
});

// ── Message Router ────────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const tabId = sender.tab?.id;

  console.log("[TruthLens] Message received:", message.type, "from tab:", tabId);

  switch (message.type) {
    // Content script reports that it has extracted text from the page
    case "EXTRACTION_COMPLETE": {
      handleExtractionComplete(tabId!, message.payload, sendResponse);
      return true; // keep channel open for async response
    }

    // Popup is asking for the current page state
    case "GET_PAGE_STATE": {
      getPageState(message.tabId, sendResponse);
      return true;
    }

    // Popup requests a fresh re-analysis (invalidate cached result)
    case "RE_ANALYZE": {
      handleReAnalyze(message.tabId, sendResponse);
      return true;
    }

    // Popup asks to open the side panel
    case "OPEN_SIDE_PANEL": {
      if (tabId) chrome.sidePanel.open({ tabId });
      sendResponse({ ok: true });
      break;
    }

    // Badge update request from content script or popup
    case "UPDATE_BADGE": {
      if (tabId) setBadge(tabId, message.payload.type, message.payload.score);
      sendResponse({ ok: true });
      break;
    }

    default:
      console.warn("[TruthLens] Unknown message type:", message.type);
  }
});

// ── Preferences Helper ────────────────────────────────────────────────────────

interface Preferences {
  highlightingEnabled: boolean;
  notificationsEnabled: boolean;
  explainLikeImFive: boolean;
  familyShieldEnabled: boolean;
  autoAnalyze: boolean;
}

function getPreferences(): Promise<Preferences> {
  return new Promise((resolve) => {
    chrome.storage.local.get(["preferences"], (result) => {
      resolve(result.preferences ?? {
        highlightingEnabled: true,
        notificationsEnabled: false,
        explainLikeImFive: false,
        familyShieldEnabled: false,
        autoAnalyze: true,
      });
    });
  });
}

// ── Extraction Handler ────────────────────────────────────────────────────────

/**
 * Called when the content script has finished extracting page text.
 * Step 2: Calls the backend, persists the result, and updates the badge.
 */
async function handleExtractionComplete(
  tabId: number,
  payload: { text: string; title: string; url: string },
  sendResponse: (r: unknown) => void
): Promise<void> {
  const { text, title, url } = payload;

  console.log(`[TruthLens] Extracted ${text.length} chars from "${title}" (${url})`);

  // Build initial page state — analysis pending
  const pageState: ExtensionPageState = {
    url,
    analysis: null,
    pendingJobId: null,
    extractedText: text,
    extractedAt: new Date().toISOString(),
  };

  // Persist for popup to read
  await chrome.storage.local.set({ [`pageState_${tabId}`]: pageState });

  // Update badge to "pending" state (spinner / indigo)
  setBadge(tabId, "pending");

  // Respond immediately — the backend call happens async below
  sendResponse({ ok: true, charCount: text.length });

  // Check if autoAnalyze is enabled
  const prefs = await getPreferences();
  if (!prefs.autoAnalyze) {
    console.log("[TruthLens] Auto-analyze disabled. Skipping backend call.");
    return;
  }

  // ── Call the backend ──────────────────────────────────────────────────────
  await runAnalysis(tabId, { text, url, title });
}

// ── Re-Analyze Handler ────────────────────────────────────────────────────────

/**
 * Called when the popup requests a fresh re-analysis (user clicked Re-analyze).
 * Reads the stored extracted text and re-runs the backend call.
 */
async function handleReAnalyze(
  tabId: number,
  sendResponse: (r: unknown) => void
): Promise<void> {
  const stored = await new Promise<ExtensionPageState | null>((resolve) => {
    chrome.storage.local.get([`pageState_${tabId}`], (result) => {
      resolve(result[`pageState_${tabId}`] ?? null);
    });
  });

  if (!stored || !stored.extractedText) {
    sendResponse({ ok: false, error: "No extracted text available for re-analysis." });
    return;
  }

  // Clear existing analysis result
  stored.analysis = null;
  stored.pendingJobId = null;
  await chrome.storage.local.set({ [`pageState_${tabId}`]: stored });
  setBadge(tabId, "pending");

  sendResponse({ ok: true });

  // Re-run analysis
  await runAnalysis(tabId, {
    text: stored.extractedText,
    url: stored.url,
    title: "", // title is not critical for re-analysis
  });
}

// ── Core Analysis Runner ──────────────────────────────────────────────────────

/**
 * Calls the backend analyzeText API and persists the result.
 * Used by both handleExtractionComplete and handleReAnalyze.
 */
async function runAnalysis(
  tabId: number,
  payload: { text: string; url: string; title?: string }
): Promise<void> {
  try {
    console.log(`[TruthLens] Calling backend for tab ${tabId}...`);

    const result = await analyzeText({
      text: payload.text,
      url: payload.url,
      title: payload.title,
    });

    console.log(
      `[TruthLens] Backend response for tab ${tabId}:`,
      `score=${result.credibility.score}`,
      `band=${result.credibility.band}`,
      `offline=${(result as any)._isLocalFallback ?? false}`
    );

    // Persist the analysis result in page state
    const current = await new Promise<ExtensionPageState | null>((resolve) => {
      chrome.storage.local.get([`pageState_${tabId}`], (r) => {
        resolve(r[`pageState_${tabId}`] ?? null);
      });
    });

    if (current) {
      current.analysis = result;
      current.pendingJobId = result.deepCheckPending ? result.jobId : null;
      await chrome.storage.local.set({ [`pageState_${tabId}`]: current });
    }

    // Update badge based on result
    setBadgeFromResult(tabId, result);

    // Apply inline highlighting if enabled and claims exist
    const prefs = await getPreferences();
    if (prefs.highlightingEnabled && result.claims && result.claims.length > 0) {
      const highlights = result.claims
        .map((c) => ({
          start: c.textOffset?.start ?? 0,
          end: c.textOffset?.end ?? 0,
          verdict: c.verdict,
          claimText: c.claim,
          originalText: c.originalText || c.claim,
          claimId: c.id,
        }));

      if (highlights.length > 0) {
        chrome.tabs.sendMessage(tabId, {
          type: "APPLY_HIGHLIGHTS",
          payload: { highlights },
        }).catch((e) => {
          console.debug("[TruthLens] Could not send highlights to content script:", e);
        });
      }
    }

  } catch (err) {
    console.error(`[TruthLens] Analysis failed for tab ${tabId}:`, err);
    // Set badge to error state — never show a false verdict
    setBadge(tabId, "error");
  }
}

// ── Page State Helpers ────────────────────────────────────────────────────────

function getPageState(
  tabId: number,
  sendResponse: (r: ExtensionPageState | null) => void
): void {
  chrome.storage.local.get([`pageState_${tabId}`], (result) => {
    sendResponse(result[`pageState_${tabId}`] ?? null);
  });
}

// ── Badge Management ─────────────────────────────────────────────────────────

type BadgeType = "neutral" | "pending" | "green" | "yellow" | "red" | "error";

const BADGE_CONFIG: Record<BadgeType, { color: string; text: string }> = {
  neutral:  { color: "#9CA3AF", text: "" },       // gray, no number
  pending:  { color: "#6366F1", text: "…" },       // indigo, ellipsis
  green:    { color: "#22C55E", text: "" },         // set dynamically
  yellow:   { color: "#EAB308", text: "" },
  red:      { color: "#EF4444", text: "" },
  error:    { color: "#6B7280", text: "!" },
};

function setBadge(tabId: number, type: BadgeType, score?: number): void {
  const cfg = BADGE_CONFIG[type];
  const text = score !== undefined ? String(Math.round(score)) : cfg.text;

  chrome.action.setBadgeBackgroundColor({ tabId, color: cfg.color });
  chrome.action.setBadgeText({ tabId, text });
}

/**
 * Step 2: Maps the backend's credibility response to the appropriate badge.
 * Handles offline fallback gracefully (gray "?" badge).
 */
function setBadgeFromResult(
  tabId: number,
  result: AnalyzeTextResponse & { _isLocalFallback?: boolean }
): void {
  // If backend was offline, show gray "?" — never a false verdict
  if ((result as any)._isLocalFallback) {
    setBadge(tabId, "neutral");
    chrome.action.setBadgeText({ tabId, text: "?" });
    return;
  }

  const { score, color } = result.credibility;
  const badgeType: BadgeType =
    color === "green"  ? "green" :
    color === "yellow" ? "yellow" :
    color === "red"    ? "red" :
    "neutral";

  setBadge(tabId, badgeType, score);
}

// ── Polling Alarm (Step 3+) ────────────────────────────────────────────────

// Placeholder: in Step 3 we create an alarm to poll /api/analyze-text/status/:jobId
// chrome.alarms.create(ALARM_POLL, { periodInMinutes: 0.1 });
// chrome.alarms.onAlarm.addListener((alarm) => {
//   if (alarm.name === ALARM_POLL) pollPendingJobs();
// });

console.log("[TruthLens] Service worker started (Step 2 — wired to backend).");
