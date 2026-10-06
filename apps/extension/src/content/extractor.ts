/**
 * extractor.ts — TruthLens Content Script: Article Text Extractor
 *
 * Runs at document_idle in the main frame.
 *
 * Responsibilities:
 *   1. Detect whether the current page is an article/news page (heuristic)
 *   2. Extract clean article text using a Readability-inspired approach
 *      (no external library dependency in the content script bundle)
 *   3. Send the extracted content to the service worker
 *   4. Respond to CONTEXT_MENU_VERIFY messages for selection-based checks
 *
 * Privacy note: Only the visible article text is sent — never cookies,
 * form data, or any page content the user hasn't intentionally requested.
 */

// ── Types ─────────────────────────────────────────────────────────────────────

interface ExtractedContent {
  text: string;
  title: string;
  url: string;
  byline: string | null;
  publishedAt: string | null;
  language: string;
  charCount: number;
  wordCount: number;
  /** True if the extractor is confident this is an article (not a homepage, etc.) */
  isArticle: boolean;
}

// ── Selectors used to locate article body ─────────────────────────────────────

/**
 * Ordered list of CSS selectors tried in sequence.
 * First match wins. Inspired by Readability.js's approach but inline.
 */
const ARTICLE_SELECTORS = [
  "article[class*='article']",
  "article[class*='story']",
  "article[class*='post']",
  "article",
  "[role='article']",
  "[role='main'] article",
  "main article",
  ".article-body",
  ".article-content",
  ".story-body",
  ".story-content",
  ".post-content",
  ".entry-content",
  ".content-body",
  "#article-body",
  "#story-body",
  "[itemprop='articleBody']",
  "[data-component='article-body']",
  // Fallback: main element
  "main",
  "[role='main']",
  "#main-content",
  "#content",
];

/** Tags whose text content we always exclude from extraction. */
const EXCLUDED_TAGS = new Set([
  "SCRIPT", "STYLE", "NAV", "HEADER", "FOOTER",
  "ASIDE", "FORM", "BUTTON", "INPUT", "SELECT",
  "TEXTAREA", "IFRAME", "NOSCRIPT", "FIGURE",
  "FIGCAPTION", "PICTURE",
]);

// ── Heuristics for "is this an article page?" ────────────────────────────────

/** Minimum word count to consider a page worth analyzing. */
const MIN_WORD_COUNT = 150;

/**
 * Returns true if the page is likely a news/blog article rather than a
 * homepage, search page, e-commerce page, etc.
 */
function isArticlePage(): boolean {
  // Open Graph type hint
  const ogType = document.querySelector<HTMLMetaElement>('meta[property="og:type"]')?.content;
  if (ogType === "article") return true;

  // Schema.org structured data
  const jsonLd = document.querySelectorAll('script[type="application/ld+json"]');
  for (const el of Array.from(jsonLd)) {
    try {
      const data = JSON.parse(el.textContent ?? "{}");
      const type = data["@type"] ?? "";
      if (
        type === "NewsArticle" ||
        type === "Article" ||
        type === "BlogPosting" ||
        type === "ReportageNewsArticle"
      ) {
        return true;
      }
    } catch {
      // malformed JSON-LD — ignore
    }
  }

  // Presence of an <article> element with meaningful content
  const article = document.querySelector("article");
  if (article && article.textContent && article.textContent.split(/\s+/).length > MIN_WORD_COUNT) {
    return true;
  }

  // URL path heuristics (contains year/month/day or /article/ /story/ /news/)
  const path = window.location.pathname;
  if (/\/\d{4}\/\d{2}\//.test(path)) return true;
  if (/\/(article|story|news|post|blog)\//i.test(path)) return true;

  return false;
}

// ── Metadata Extraction ───────────────────────────────────────────────────────

function getPageTitle(): string {
  return (
    document.querySelector<HTMLMetaElement>('meta[property="og:title"]')?.content ||
    document.querySelector<HTMLMetaElement>('meta[name="twitter:title"]')?.content ||
    document.title ||
    ""
  ).trim();
}

function getByline(): string | null {
  const candidates = [
    document.querySelector('[rel="author"]'),
    document.querySelector('[itemprop="author"]'),
    document.querySelector('.byline'),
    document.querySelector('.author'),
    document.querySelector('[class*="byline"]'),
    document.querySelector('[class*="author"]'),
    document.querySelector<HTMLMetaElement>('meta[name="author"]'),
  ];
  for (const el of candidates) {
    if (!el) continue;
    const text = el instanceof HTMLMetaElement ? el.content : el.textContent;
    if (text && text.trim().length > 0 && text.trim().length < 100) {
      return text.trim();
    }
  }
  return null;
}

function getPublishedAt(): string | null {
  const el =
    document.querySelector<HTMLMetaElement>('meta[property="article:published_time"]') ||
    document.querySelector<HTMLMetaElement>('meta[name="publication_date"]') ||
    document.querySelector<HTMLTimeElement>("time[datetime]");

  if (el instanceof HTMLMetaElement) return el.content || null;
  if (el instanceof HTMLTimeElement) return el.dateTime || null;
  return null;
}

function getLanguage(): string {
  return (
    document.documentElement.lang ||
    document.querySelector<HTMLMetaElement>('meta[http-equiv="content-language"]')?.content ||
    "en"
  ).slice(0, 2).toLowerCase();
}

// ── Main Text Extraction ──────────────────────────────────────────────────────

/**
 * Walks a DOM element and collects visible text, skipping excluded tags.
 * Preserves paragraph structure by joining block-level elements with newlines.
 */
function extractTextFromElement(element: Element): string {
  const parts: string[] = [];

  function walk(node: Node): void {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.textContent?.trim();
      if (text) parts.push(text);
      return;
    }

    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const el = node as Element;

    // Skip excluded tags
    if (EXCLUDED_TAGS.has(el.tagName)) return;

    // Skip hidden elements
    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") return;

    // Add paragraph breaks for block elements
    const isBlock = ["P", "H1", "H2", "H3", "H4", "H5", "H6", "LI", "BLOCKQUOTE", "DIV"]
      .includes(el.tagName);

    if (isBlock && parts.length > 0) {
      parts.push("\n");
    }

    for (const child of Array.from(el.childNodes)) {
      walk(child);
    }

    if (isBlock) {
      parts.push("\n");
    }
  }

  walk(element);

  return parts.join(" ")
    .replace(/[ \t]+/g, " ")       // collapse horizontal whitespace
    .replace(/\n{3,}/g, "\n\n")    // max two consecutive newlines
    .trim();
}

/**
 * Attempts each selector in ARTICLE_SELECTORS to find the best article container.
 * Falls back to <body> if nothing specific is found.
 */
function findArticleContainer(): Element {
  for (const selector of ARTICLE_SELECTORS) {
    const el = document.querySelector(selector);
    if (el && (el.textContent?.split(/\s+/).length ?? 0) > MIN_WORD_COUNT) {
      return el;
    }
  }
  return document.body;
}

/** Full extraction pipeline. Returns structured content. */
function extractContent(): ExtractedContent {
  const container = findArticleContainer();
  const text = extractTextFromElement(container);
  const words = text.split(/\s+/).filter(Boolean);

  return {
    text,
    title: getPageTitle(),
    url: window.location.href,
    byline: getByline(),
    publishedAt: getPublishedAt(),
    language: getLanguage(),
    charCount: text.length,
    wordCount: words.length,
    isArticle: isArticlePage(),
  };
}

// ── Message Handling ──────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "CONTEXT_MENU_VERIFY") {
    // User right-clicked and chose "Verify with TruthLens"
    const { selectionText } = message.payload;

    if (selectionText) {
      // If text was selected, send just the selection
      console.log("[TruthLens] Context menu: verifying selected text:", selectionText.slice(0, 80));
      chrome.runtime.sendMessage({
        type: "EXTRACTION_COMPLETE",
        payload: {
          text: selectionText,
          title: getPageTitle(),
          url: window.location.href,
        },
      });
    } else {
      // Otherwise, extract full article
      const content = extractContent();
      chrome.runtime.sendMessage({
        type: "EXTRACTION_COMPLETE",
        payload: content,
      });
    }

    sendResponse({ ok: true });
    return true;
  }

  if (message.type === "REQUEST_EXTRACTION") {
    // Popup can explicitly request (re-)extraction
    const content = extractContent();
    sendResponse(content);
    return true;
  }
});

// ── Auto-extraction on page load ──────────────────────────────────────────────

/**
 * Runs automatically on document_idle.
 * Only sends data if the page looks like an article and meets minimum length.
 * Does NOT auto-extract on homepages, search results, e-commerce, etc.
 */
(function autoExtract() {
  // Don't run on extension pages or browser internals
  const url = window.location.href;
  if (url.startsWith("chrome://") || url.startsWith("chrome-extension://")) return;
  if (url.startsWith("about:") || url.startsWith("moz-extension://")) return;

  const content = extractContent();

  console.log(
    `[TruthLens] Extracted: ${content.wordCount} words | isArticle: ${content.isArticle} | "${content.title.slice(0, 60)}"`
  );

  // Only auto-trigger the analysis pipeline if this looks like an article
  if (!content.isArticle || content.wordCount < MIN_WORD_COUNT) {
    console.log("[TruthLens] Page does not appear to be an article. Skipping auto-analysis.");
    return;
  }

  // Send to service worker — which will update badge and (Step 2+) call backend
  chrome.runtime.sendMessage(
    {
      type: "EXTRACTION_COMPLETE",
      payload: {
        text: content.text,
        title: content.title,
        url: content.url,
      },
    },
    (response) => {
      if (chrome.runtime.lastError) {
        console.warn("[TruthLens] Service worker not ready:", chrome.runtime.lastError.message);
        return;
      }
      console.log("[TruthLens] Service worker acknowledged extraction:", response);
    }
  );
})();
