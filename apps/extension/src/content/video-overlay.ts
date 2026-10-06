/**
 * video-overlay.ts — TruthLens Content Script: Video Element Badge Overlay
 *
 * Runs in ALL frames (including iframes) at document_idle.
 * Monitors <video> elements and, once deepfake analysis is complete (Step 9),
 * injects an unobtrusive badge overlay indicating confidence.
 *
 * Step 1: Infrastructure only — observes video elements and logs them.
 * Step 9: Badge rendering and deepfake result wiring.
 *
 * Design constraints:
 *   - Badge is OVERLAY only — does not pause, modify, or interfere with video
 *   - Uses a Shadow DOM to prevent page CSS from overriding badge styles
 *   - Badge is dismissible by the user
 */

// ── Types ─────────────────────────────────────────────────────────────────────

interface VideoBadgeData {
  src: string;
  manipulationScore: number; // 0–100
  isFlagged: boolean;
  confidenceRange: string;
  explanation: string;
}

// ── Tracked Videos ────────────────────────────────────────────────────────────

/** Set of <video> src values already queued for analysis (avoids duplicates). */
const trackedVideos = new Set<string>();

// ── Badge Injection ───────────────────────────────────────────────────────────

/**
 * Injects a floating badge overlay above a <video> element.
 * Uses Shadow DOM so page styles cannot bleed in.
 */
function injectVideoBadge(videoEl: HTMLVideoElement, data: VideoBadgeData): void {
  // Don't inject twice
  if (videoEl.dataset.tlBadged === "true") return;
  videoEl.dataset.tlBadged = "true";

  // Wrap the video if it isn't already inside a relative-position container
  let wrapper = videoEl.parentElement;
  if (!wrapper || getComputedStyle(wrapper).position === "static") {
    wrapper = document.createElement("div");
    wrapper.style.cssText = "position:relative;display:inline-block;";
    videoEl.parentNode?.insertBefore(wrapper, videoEl);
    wrapper.appendChild(videoEl);
  }

  // Badge host element
  const host = document.createElement("div");
  host.style.cssText = `
    position: absolute;
    top: 8px;
    left: 8px;
    z-index: 2147483647;
  `;

  // Shadow root for style isolation
  const shadow = host.attachShadow({ mode: "open" });

  const color = data.isFlagged
    ? (data.manipulationScore >= 70 ? "#EF4444" : "#EAB308")
    : "#22C55E";

  const label = data.isFlagged ? "⚠ Deepfake Risk" : "✓ Appears Authentic";

  shadow.innerHTML = `
    <style>
      .badge {
        display: flex;
        align-items: center;
        gap: 6px;
        background: rgba(15, 23, 42, 0.88);
        border: 1.5px solid ${color};
        color: ${color};
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        font-size: 11px;
        font-weight: 600;
        padding: 4px 8px;
        border-radius: 6px;
        backdrop-filter: blur(4px);
        cursor: pointer;
        user-select: none;
        transition: opacity 0.2s;
      }
      .badge:hover { opacity: 0.7; }
      .badge .dot {
        width: 7px; height: 7px;
        border-radius: 50%;
        background: ${color};
        flex-shrink: 0;
      }
      .dismiss {
        margin-left: 4px;
        opacity: 0.5;
        cursor: pointer;
      }
      .dismiss:hover { opacity: 1; }
    </style>
    <div class="badge" title="${data.confidenceRange} — ${data.explanation}">
      <span class="dot"></span>
      ${label}
      <span class="dismiss" title="Dismiss badge">✕</span>
    </div>
  `;

  // Dismiss on click of ✕
  shadow.querySelector(".dismiss")?.addEventListener("click", (e) => {
    e.stopPropagation();
    host.remove();
  });

  // Click on badge → open side panel with details (Step 9)
  shadow.querySelector(".badge")?.addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "OPEN_SIDE_PANEL" });
  });

  wrapper.appendChild(host);
  console.log(`[TruthLens] Video badge injected: ${label} (${data.manipulationScore}%)`);
}

// ── Video Discovery ───────────────────────────────────────────────────────────

function processVideoElement(video: HTMLVideoElement): void {
  const src = video.src || video.currentSrc || video.querySelector("source")?.src;
  if (!src || trackedVideos.has(src)) return;

  trackedVideos.add(src);
  console.log(`[TruthLens] Found video: ${src.slice(0, 80)}`);

  // Step 9: Trigger backend deepfake analysis
  // chrome.runtime.sendMessage({ type: "ANALYZE_VIDEO", payload: { src } });
}

/** Scan all existing <video> elements on the page. */
function scanVideos(): void {
  document.querySelectorAll<HTMLVideoElement>("video").forEach(processVideoElement);
}

/** Watch for dynamically added <video> elements (SPAs, lazy-loaded content). */
const videoObserver = new MutationObserver((mutations) => {
  for (const mutation of mutations) {
    for (const node of Array.from(mutation.addedNodes)) {
      if (node instanceof HTMLVideoElement) {
        processVideoElement(node);
      } else if (node instanceof Element) {
        node.querySelectorAll<HTMLVideoElement>("video").forEach(processVideoElement);
      }
    }
  }
});

// ── Message Handling ──────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "APPLY_VIDEO_BADGE") {
    // Step 9: Service worker sends badge data after deepfake analysis completes
    const data: VideoBadgeData = message.payload;
    const video = document.querySelector<HTMLVideoElement>(`video[src="${data.src}"]`)
      ?? document.querySelector<HTMLVideoElement>("video");

    if (video) {
      injectVideoBadge(video, data);
      sendResponse({ ok: true });
    } else {
      sendResponse({ ok: false, reason: "video_not_found" });
    }
    return true;
  }
});

// ── Init ─────────────────────────────────────────────────────────────────────

scanVideos();
videoObserver.observe(document.body, { childList: true, subtree: true });
console.log("[TruthLens] Video overlay watcher initialized.");
