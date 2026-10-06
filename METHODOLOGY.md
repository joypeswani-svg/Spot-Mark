# 🔬 TruthLens: Technical Methodology & System Architecture

**Document Type:** Technical Methodology & System Design  
**Project:** TruthLens — Real-Time Misinformation, Deepfake, and Clickbait Detection System  
**Version:** 0.2.0  
**Date:** August 23, 2026  

---

## 摘要 (Abstract)

TruthLens is a multi-layered, real-time misinformation and deepfake detection platform designed to evaluate web content credibility without compromising user privacy or browsing performance. Operating through a Chrome/Edge Manifest V3 browser extension and powered by an asynchronous FastAPI microservices backend, TruthLens employs a **dual-tier hybrid analysis framework**: a millisecond **Fast-Pass Classifier** for instant writing-style and domain reputation scoring, coupled with an asynchronous **Deep Fact-Checking Pipeline** utilizing Large Language Models (LLMs), multi-source fact-checking APIs, the GDELT international news corpus, and vector similarity search over historical fact-check databases.

---

## 1. System Architecture & High-Level Workflow

TruthLens utilizes a decoupled client-server architecture. All computationally expensive models and external API keys are hosted on the backend, ensuring zero secret leakage to client web extensions.

```
┌──────────────────────────────────────────────────────────────────┐
│                      Client Surface (Chrome/Edge MV3)             │
│   DOM Extractor (extractor.ts) ──► Inline Highlighter (highlighter.ts)│
└─────────────────────────────────┬────────────────────────────────┘
                                  │ HTTPS (JSON API)
                                  ▼
┌──────────────────────────────────────────────────────────────────┐
│                         FastAPI Backend                           │
│                                                                  │
│  ┌───────────────────────────┐      ┌──────────────────────────┐ │
│  │ Tier 1: Fast-Pass (~200ms)│      │ Tier 2: Deep Fact-Check  │ │
│  │ - DistilBERT ONNX Style   │      │ - Multi-LLM Claim Extract│ │
│  │ - Domain Reputation DB    │      │ - Google Fact Check API  │ │
│  └─────────────┬─────────────┘      │ - GDELT News Corpus      │ │
│                │                    │ - pgvector Search        │ │
│                │                    └────────────┬─────────────┘ │
│                └──────────────────┬──────────────┘               │
│                                   ▼                              │
│                   Composite Credibility Scorer                   │
└───────────────────────────────────┬──────────────────────────────┘
                                    ▼
                         Response & DOM Annotations
```

---

## 2. Content Extraction & Client Infrastructure

### 2.1 DOM Extractor (`apps/extension/src/content/extractor.ts`)
* **Text Normalization:** Scans the active document using semantic HTML5 tags (`<article>`, `<main>`, `<p>`) to extract clean body text while filtering out advertisements, navigation bars, comments, and boilerplate text.
* **Metadata Extraction:** Extracts OpenGraph and Schema.org metadata (title, author, publishing date, canonical URL).
* **Privacy Preservation:** Content extraction occurs strictly on active user interaction or explicit domain whitelist policy; full browsing histories are never transmitted.

### 2.2 Non-Destructive DOM Highlighter (`apps/extension/src/content/highlighter.ts`)
* **CSS Custom Highlight API:** Uses Chrome's native CSS Highlight API (`CSS.highlights`) with HTML `<mark>` fallback.
* **Zero DOM Mutation:** Annotations apply non-destructive styling overlays on text ranges without modifying underlying element nodes or event listeners.

---

## 3. Dual-Tier Misinformation Detection Pipeline

### 3.1 Tier 1: Fast-Pass Analysis Engine (~200ms Latency)

The Fast-Pass Engine generates immediate visual feedback while deep analysis completes in the background.

1. **Writing-Style & Sensationalism Classifier (`app/services/style_classifier.py`):**
   * **Model Architecture:** Fine-tuned DistilBERT model exported to ONNX format (`distilbert_fakenews.onnx`).
   * **Feature Detection:** Evaluates sensationalist linguistic patterns, excessive exclamation, clickbait title structures, ALL-CAPS emotional outrage triggers, and attribution presence.
   * **Scoring Function:** Returns a normalized style confidence score $S_{\text{style}} \in [0, 100]$.

2. **Domain Reputation Engine (`app/services/domain_reputation.py`):**
   * **Database Lookup:** Cross-references the canonical publisher hostname against a indexed dataset of news outlets, satire sites, and known misinformation domains.
   * **Subdomain Fallback:** Resolves subdomains (e.g. `edition.cnn.com` $\rightarrow$ `cnn.com`) for robust evaluation.
   * **Satire Flagging:** Identifies registered satire publications (e.g. *The Onion*) to prevent false-positive misinformation flagging.
   * **Scoring Function:** Returns domain credibility score $S_{\text{domain}} \in [0, 100]$.

---

### 3.2 Tier 2: Deep Fact-Checking & Claim Verification (2–8s Latency)

#### A. Factual Claim Extraction & Decomposition (`app/services/claim_extractor.py`)
Raw article text is decomposed into discrete, verifiable atomic claims using a multi-provider fallback cascade:

$$\text{Extract Cascade} = \text{Groq LPU} \longrightarrow \text{Gemini API} \longrightarrow \text{Local LM Studio} \longrightarrow \text{Ollama} \longrightarrow \text{Heuristic Regex}$$

* **Structured LLM Schema:** The LLM is constrained via JSON schema output to isolate verifiable factual assertions:
```json
{
  "claims": [
    {
      "claim": "Clear standalone statement of the factual claim",
      "originalText": "Exact original sentence from article text"
    }
  ]
}
```
* **Local LLM & LM Studio Resilience:** Handles both dictionary object schemas and raw string array outputs returned by local open-weight models (e.g., Qwen 3 8B, Llama 3.1 8B). Cleans reasoning tags (`<think>...</think>`) and code block fences.
* **Character Offset Mapping:** Computes exact character start and end indices (`startOffset`, `endOffset`) in the original text to enable precise client-side inline highlighting.

#### B. Multi-Source Fact Verification
1. **Google Fact Check Tools API (`app/services/fact_checker.py`):**
   * Queries independent fact-checking organizations (PolitiFact, Alt News, Snopes, Factly, etc.).
   * Extracts publisher rating labels, claim review URLs, and textual verdicts.
2. **GDELT International News Corpus (`app/services/gdelt_service.py`):**
   * Performs real-time search across the GDELT Project API to evaluate global news coverage volume and corroboration across international press outlets.
3. **`pgvector` Semantic Similarity Search (`app/services/vector_search.py`):**
   * Generates text embeddings using `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions).
   * Executes cosine similarity search over cached fact-check database tables using PostgreSQL `pgvector`:
     $$\text{Cosine Similarity} = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\| \|\mathbf{v}\|}$$

---

## 4. Composite Credibility Scoring Algorithm

The final credibility score $S_{\text{composite}} \in [0, 100]$ is computed via a weighted linear combination of four normalized sub-scores:

$$S_{\text{composite}} = w_1 \cdot S_{\text{fact}} + w_2 \cdot S_{\text{gdelt}} + w_3 \cdot S_{\text{domain}} + w_4 \cdot S_{\text{style}}$$

### Weight Distribution:
* **$w_1 = 0.50$ (Claim Verification):** Highest weight given to direct fact-check publisher reviews and pgvector semantic matches.
* **$w_2 = 0.20$ (Global Corroboration):** GDELT news volume and press coverage presence.
* **$w_3 = 0.15$ (Domain Reputation):** Historical publisher trust score.
* **$w_4 = 0.15$ (Writing Style Classifier):** Linguistic style and sensationalism detection.

---

### Classification Bands & Decision Matrix

TruthLens enforces strict non-binary classification and explicitly avoids claiming 100% absolute certainty:

| Score Range | Verdict Band | Badge Color | Interpretation |
|---|---|---|---|
| **80 – 100** | **Verified** | 🟢 Green | High confidence; claims corroborated by reputable fact-checkers and news databases. |
| **50 – 79** | **Caution / Misleading** | 🟡 Yellow | Mixed context, clickbait elements, or insufficient corroborating sources. |
| **0 – 49** | **Likely False** | 🔴 Red | High probability of misinformation; claims directly debunked by credible sources. |
| **N/A** | **Unverified** | 🔘 Gray | Network error or offline fallback state (never generates false verdicts). |

---

## 5. Media & Deepfake Detection Adapter Framework

TruthLens uses an abstract adapter design pattern (`app/adapters/base_deepfake.py`) to support pluggable deepfake detection providers for images, video frames, and audio clips:

```python
class BaseDeepfakeAdapter(ABC):
    @abstractmethod
    async def analyze_image(self, image_bytes: bytes) -> Dict[str, Any]: pass
    
    @abstractmethod
    async def analyze_video(self, video_url: str) -> Dict[str, Any]: pass
```

* **Local Adapter (`local_deepfake.py`):** Open-source HuggingFace model implementation running locally (zero operational cost).
* **Commercial Paid Adapter (`hive_deepfake.py`):** Enterprise integration with Hive Moderation / Sensity API, configurable via environment settings.

---

## 6. Moderation, Domain Shielding & PIB Escalation

1. **Domain Blocking (`routers/block.py`):** Users can toggle domain blacklists. When active, `shield.ts` injects a visual warning overlay over blacklisted domain pages.
2. **Press Information Bureau (PIB) Escalation Pipeline (`routers/report.py`):**
   * Automatically formats user-reported misinformation and constructs direct escalation links to India's official **PIB Fact Check** channels:
     * **WhatsApp API:** `https://wa.me/918799711259?text=...`
     * **Email Payload Export:** `mailto:pibfactcheck@gmail.com?subject=...`
     * **Web Portal:** Direct link to `https://factcheck.pib.gov.in`

---

## 7. Experimental Evaluation & Verification

The pipeline logic is verified through automated test suites in `apps/backend/tests/`:
* `test_step3.py`: Evaluates claim extraction accuracy, GDELT keyword parsing, and synthesizer output structure.
* `test_step5_services.py`: Tests domain reputation lookups, satire classification, and clickbait style detection.
* `test_step6_moderation.py`: Tests User Reporting endpoints, PIB WhatsApp link generation, and domain block/unblock state persistence.

---

## 8. Summary of Methodological Principles

1. 🔐 **Zero Client Secrets:** All API keys and ML models remain strictly server-side.
2. 🎯 **Probabilistic Guidance:** Never claims 100% certainty; always cites sources and confidence metrics.
3. 🛡️ **Non-Destructive UI:** Annotates web pages without mutating underlying DOM nodes.
4. 🔌 **Pluggable Architecture:** Fallback support across LLM providers and deepfake detection engines.
5. 🇮🇳 **Official Escalation Integration:** Built-in escalation to recognized public fact-checking bodies (PIB).
