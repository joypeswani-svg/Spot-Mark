/**
 * @truthlens/types
 * Shared TypeScript types used across the extension, mobile app, and backend.
 * All API response shapes live here so both clients stay in sync.
 */

// ─── Credibility ────────────────────────────────────────────────────────────

/** Composite 0–100 score with human-readable band. */
export type CredibilityBand = "verified" | "caution" | "likely-false" | "unverified";

export interface CredibilityScore {
  /** 0–100 composite score. Higher = more credible. */
  score: number;
  /** Human-readable band derived from score. */
  band: CredibilityBand;
  /**
   * Color token for UI rendering.
   * green = 80–100, yellow = 50–79, red = 0–49, gray = unverified
   */
  color: "green" | "yellow" | "red" | "gray";
  /** One-sentence plain-English explanation of why this score was assigned. */
  explanation: string;
  /** Breakdown of sub-scores used in the composite (0–100 each). */
  breakdown: {
    claimVerification: number;   // 50% weight
    domainReputation: number;    // 20% weight
    styleClassifier: number;     // 15% weight
    crossCorroboration: number;  // 15% weight
  };
}

// ─── Claims ─────────────────────────────────────────────────────────────────

export type ClaimVerdict = "TRUE" | "FALSE" | "MISLEADING" | "UNVERIFIED";

/** A single atomic factual claim extracted from article content. */
export interface Claim {
  id: string;
  /** The original sentence(s) the claim was extracted from. */
  originalText: string;
  /** Cleaned, concise statement of the factual claim. */
  claim: string;
  verdict: ClaimVerdict;
  /** 0–100 confidence in the verdict. */
  confidence: number;
  /** Plain-English explanation of the verdict. */
  explanation: string;
  /** 1–3 cited sources backing the verdict. */
  sources: Source[];
  /** Where in the original article this claim appears (for inline highlighting). */
  textOffset?: { start: number; end: number };
}

// ─── Sources ────────────────────────────────────────────────────────────────

export interface Source {
  title: string;
  url: string;
  publisher: string;
  /** ISO 8601 date string, if available. */
  publishedAt?: string;
  /** One-sentence summary of what the source says. */
  summary: string;
  /** Credibility rating of the source itself, if known. */
  sourceCredibility?: "high" | "medium" | "low" | "unknown";
}

// ─── Domain Reputation ──────────────────────────────────────────────────────

export type BiasLean = "far-left" | "left" | "center-left" | "center" | "center-right" | "right" | "far-right" | "unknown";
export type FactualityRating = "very-high" | "high" | "mostly-factual" | "mixed" | "low" | "very-low" | "satire" | "unknown";
export type OwnershipType = "state-media" | "corporate" | "independent" | "nonprofit" | "unknown";

export interface DomainReputation {
  domain: string;
  biasLean: BiasLean;
  factualityRating: FactualityRating;
  ownershipType: OwnershipType;
  /** Human-readable owner/funder name if known. */
  ownerName?: string;
  /** True for known satire/parody outlets — these should NEVER be flagged as fake news. */
  isSatire: boolean;
  /** Notes about the outlet, e.g., "State-funded broadcaster". */
  notes?: string;
}

// ─── Analysis Request / Response ────────────────────────────────────────────

export interface AnalyzeTextRequest {
  /** Full extracted article text. */
  text: string;
  /** URL the content was taken from, used for domain lookup. */
  url?: string;
  /** Page title for context. */
  title?: string;
  /** ISO 639-1 language code, e.g. "en", "hi". Detected automatically if omitted. */
  language?: string;
}

export interface AnalyzeTextResponse {
  /** Unique ID for this analysis job, used for polling async deep-check. */
  jobId: string;
  /**
   * "fast" = DistilBERT first-pass result (available immediately).
   * "deep" = full LLM + Fact Check result (may be async).
   */
  resultType: "fast" | "deep";
  credibility: CredibilityScore;
  claims: Claim[];
  domainReputation?: DomainReputation;
  /** When true, the deep-check is still running; poll /api/analyze-text/status/:jobId */
  deepCheckPending: boolean;
  /** ISO 8601 timestamp. */
  analyzedAt: string;
  /** Whether the result was served from cache. */
  cached: boolean;
}

// ─── Media Analysis ─────────────────────────────────────────────────────────

export type DeepfakeProvider = "local" | "hive" | "sensity" | "reality-defender";

export interface MediaAnalysisResult {
  jobId: string;
  mediaType: "image" | "video" | "audio";
  /** 0–100: probability the media is AI-generated/manipulated. */
  manipulationScore: number;
  /** Whether we consider this manipulated based on score threshold. */
  isFlagged: boolean;
  /** Which detection provider was used. */
  provider: DeepfakeProvider;
  /**
   * IMPORTANT: confidence ranges, not exact values — never over-promise accuracy.
   * e.g. "60–75% confidence (moderate)"
   */
  confidenceRange: string;
  explanation: string;
  /** Metadata findings (EXIF anomalies, codec artifacts, etc.) */
  metadataFindings?: string[];
  analyzedAt: string;
}

// ─── Report & Block ──────────────────────────────────────────────────────────

/**
 * Report categories — user must pick at least one.
 * These map to the correct reporting criteria for each platform.
 */
export type ReportCategory =
  | "false-misleading"
  | "manipulated-media"
  | "impersonation"
  | "health-misinfo"
  | "election-civic-misinfo"
  | "incitement-hate-speech"
  | "spam-scam";

export interface ReportRequest {
  contentUrl: string;
  categories: ReportCategory[];
  /** The jobId of the analysis backing this report. */
  analysisJobId: string;
  /** Platform hint to generate the correct deep-link. */
  platform?: "facebook" | "twitter" | "youtube" | "instagram" | "tiktok" | "whatsapp" | "other";
}

export interface ReportResponse {
  /** Auto-generated evidence summary for copy-paste into platform report forms. */
  summary: string;
  /** Platform-specific deep-link(s) to the reporting dialog. */
  reportLinks: Array<{
    label: string;   // e.g. "Report on Facebook"
    url: string;
    notes?: string;  // e.g. "Select 'False Information' in the dropdown"
  }>;
}

export interface BlockRequest {
  /** Domain, account handle, or channel URL to block within TruthLens. */
  target: string;
  targetType: "domain" | "account" | "channel";
  /** If true and family sync is enabled, propagate to linked family accounts. */
  extendToFamily?: boolean;
}

// ─── Trending ───────────────────────────────────────────────────────────────

export interface TrendingFlag {
  id: string;
  headline: string;
  claim: string;
  verdict: ClaimVerdict;
  credibilityScore: number;
  shareCount: number;
  /** ISO 8601 */
  firstSeenAt: string;
  topSources: Source[];
}

// ─── Community Notes ─────────────────────────────────────────────────────────

export interface CommunityNote {
  id: string;
  contentUrl: string;
  note: string;
  verdict: ClaimVerdict;
  /** Contributor reputation 0–100. Higher weight in aggregation. */
  contributorReputation: number;
  upvotes: number;
  downvotes: number;
  createdAt: string;
}

// ─── Extension-specific ──────────────────────────────────────────────────────

/** Stored in chrome.storage.local for quick badge rendering. */
export interface ExtensionPageState {
  url: string;
  /** null = not yet analyzed */
  analysis: AnalyzeTextResponse | null;
  /** Pending deep-check job IDs to poll */
  pendingJobId: string | null;
  extractedText: string;
  extractedAt: string;
}

export interface BlockList {
  domains: string[];
  accounts: string[];
  channels: string[];
  updatedAt: string;
}
