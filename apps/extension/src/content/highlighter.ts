/**
 * highlighter.ts — TruthLens Content Script: Inline Sentence Highlighter
 *
 * Runs at document_idle. In Step 1 this is a stub that sets up the
 * infrastructure. Real highlighting (debounced, claim-level) is wired in Step 4
 * once we have actual claim offsets from the backend.
 *
 * Architecture:
 *   - Uses a CSS Custom Highlight API where supported (Chrome 105+), with a
 *     <mark> element fallback for older browsers
 *   - NEVER modifies the underlying DOM text — only overlays visual styles
 *   - Listens for APPLY_HIGHLIGHTS messages from the popup/service worker
 *   - Clears highlights on navigation (handled by CLEAR_HIGHLIGHTS message)
 *
 * Privacy: highlights are derived purely from local claim offset data;
 * no page content leaves the browser in this script.
 */

// ── Types ─────────────────────────────────────────────────────────────────────

interface HighlightInstruction {
  /** Start char offset in the extracted text (maps to DOM position). */
  start: number;
  /** End char offset. */
  end: number;
  /** Verdict determines highlight color. */
  verdict: "TRUE" | "FALSE" | "MISLEADING" | "UNVERIFIED";
  /** Claim text for tooltip. */
  claimText: string;
  originalText?: string;
  claimId: string;
}

// ── CSS Injection ─────────────────────────────────────────────────────────────

/**
 * Inject highlight styles into the page.
 * Uses a <style> tag in the document head, isolated under a predictable
 * class namespace to avoid collisions with page styles.
 */
function injectStyles(): void {
  if (document.getElementById("truthlens-styles")) return;

  const style = document.createElement("style");
  style.id = "truthlens-styles";
  style.textContent = `
    /* TruthLens inline highlights — non-destructive overlay */
    .tl-highlight {
      border-radius: 2px;
      cursor: pointer;
      transition: opacity 0.15s ease;
      position: relative;
    }
    .tl-highlight:hover { opacity: 0.85; }

    /* Verdict colors — deliberately subtle, not garish */
    .tl-highlight--false       { background: rgba(239, 68, 68, 0.18); border-bottom: 2px solid #EF4444; }
    .tl-highlight--misleading  { background: rgba(234, 179, 8, 0.18);  border-bottom: 2px solid #EAB308; }
    .tl-highlight--unverified  { background: rgba(107, 114, 128, 0.15); border-bottom: 2px dashed #9CA3AF; }
    .tl-highlight--true        { background: rgba(34, 197, 94, 0.12);  border-bottom: 2px solid #22C55E; }

    /* Tooltip on hover */
    .tl-tooltip {
      display: none;
      position: absolute;
      bottom: calc(100% + 4px);
      left: 0;
      background: #1F2937;
      color: #F9FAFB;
      font-size: 12px;
      line-height: 1.4;
      padding: 6px 10px;
      border-radius: 6px;
      white-space: nowrap;
      max-width: 280px;
      white-space: normal;
      z-index: 2147483647;
      box-shadow: 0 4px 16px rgba(0,0,0,0.3);
      pointer-events: none;
    }
    .tl-highlight:hover .tl-tooltip { display: block; }
  `;
  document.head.appendChild(style);
}

// ── Highlight Store ───────────────────────────────────────────────────────────

/** Tracks injected <mark> elements so we can clean them up. */
const activeHighlights: HTMLElement[] = [];

function clearHighlights(): void {
  for (const el of activeHighlights) {
    // Unwrap: replace <mark> with its text content
    const parent = el.parentNode;
    if (!parent) continue;
    while (el.firstChild) {
      parent.insertBefore(el.firstChild, el);
    }
    parent.removeChild(el);
    parent.normalize();
  }
  activeHighlights.length = 0;
  console.log("[TruthLens] Highlights cleared.");
}

// ── DOM Text Node Walker ──────────────────────────────────────────────────────

/**
 * Builds a flat list of all text nodes in the article body,
 * with their cumulative character offsets — needed to map
 * backend char offsets → DOM positions for <mark> wrapping.
 *
 * This is a Step 4 utility; prepared here so the architecture is in place.
 */
interface TextNodeEntry {
  node: Text;
  start: number;
  end: number;
}

function collectTextNodes(root: Element): TextNodeEntry[] {
  const entries: TextNodeEntry[] = [];
  let offset = 0;

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (!parent) return NodeFilter.FILTER_REJECT;
      const tag = parent.tagName;
      if (["SCRIPT", "STYLE", "NOSCRIPT"].includes(tag)) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    },
  });

  let node = walker.nextNode() as Text | null;
  while (node) {
    const len = node.textContent?.length ?? 0;
    entries.push({ node, start: offset, end: offset + len });
    offset += len;
    node = walker.nextNode() as Text | null;
  }

  return entries;
}

// ── Highlight Application (Step 4 entry point) ───────────────────────────────

/**
 * Wraps the specified text ranges in the article with <mark> elements.
 * Called by the message handler below when claim offsets arrive from backend.
 *
 * Step 1: This function is scaffolded but not invoked (no real offsets yet).
 */
function applyHighlights(instructions: HighlightInstruction[], articleRoot: Element): void {
  clearHighlights();
  injectStyles();

  const textNodes = collectTextNodes(articleRoot);

  for (const instr of instructions) {
    let highlighted = false;

    // 1. Try offset range matching
    if (instr.end > instr.start) {
      for (const entry of textNodes) {
        if (entry.end <= instr.start || entry.start >= instr.end) continue;

        const localStart = Math.max(instr.start - entry.start, 0);
        const localEnd = Math.min(instr.end - entry.start, entry.node.length);

        try {
          const range = document.createRange();
          range.setStart(entry.node, localStart);
          range.setEnd(entry.node, localEnd);

          const mark = document.createElement("mark");
          mark.className = `tl-highlight tl-highlight--${instr.verdict.toLowerCase()}`;
          mark.dataset.claimId = instr.claimId;
          mark.title = `[${instr.verdict}] ${instr.claimText}`;

          range.surroundContents(mark);
          activeHighlights.push(mark);
          highlighted = true;
        } catch (e) {
          console.warn("[TruthLens] Could not wrap range by offset:", e);
        }
      }
    }

    // 2. Fallback: string search matching across text nodes for original claim text
    if (!highlighted) {
      const searchStr = (instr.originalText || instr.claimText).trim();
      if (searchStr.length < 5) continue;

      for (const entry of textNodes) {
        const text = entry.node.textContent || "";
        const idx = text.toLowerCase().indexOf(searchStr.toLowerCase());
        if (idx !== -1) {
          try {
            const range = document.createRange();
            range.setStart(entry.node, idx);
            range.setEnd(entry.node, idx + searchStr.length);

            const mark = document.createElement("mark");
            mark.className = `tl-highlight tl-highlight--${instr.verdict.toLowerCase()}`;
            mark.dataset.claimId = instr.claimId;
            mark.title = `[${instr.verdict}] ${instr.claimText}`;

            range.surroundContents(mark);
            activeHighlights.push(mark);
            break;
          } catch (e) {
            console.warn("[TruthLens] Could not wrap by string search:", e);
          }
        }
      }
    }
  }

  console.log(`[TruthLens] Applied ${activeHighlights.length} claim highlights to page.`);
}

// ── Message Listener ──────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  switch (message.type) {
    case "APPLY_HIGHLIGHTS": {
      // Step 4+: payload contains HighlightInstruction[]
      const articleRoot = document.querySelector("article") ?? document.body;
      applyHighlights(message.payload.highlights, articleRoot);
      sendResponse({ ok: true, count: activeHighlights.length });
      return true;
    }

    case "CLEAR_HIGHLIGHTS": {
      clearHighlights();
      sendResponse({ ok: true });
      return true;
    }
  }
});

// ── Init ─────────────────────────────────────────────────────────────────────

injectStyles();
console.log("[TruthLens] Highlighter initialized. Awaiting claim offsets from backend.");
