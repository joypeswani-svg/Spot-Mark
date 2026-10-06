# 🛡️ TruthLens — Detailed Project Progress Report

**Date:** August 23, 2026  
**Version:** 0.2.0  
**Project Overview:**  
TruthLens is a real-time fake news, deepfake, AI-generated image/video, and voice clone detection platform. It operates across multiple user surfaces (Chrome/Edge Browser Extension, with planned Expo Mobile App) powered by a single FastAPI backend and multi-stage ML analysis pipeline.

---

## 📑 Table of Contents
1. [Monorepo & Infrastructure Architecture](#1-monorepo--infrastructure-architecture)
2. [Browser Extension (Chrome/Edge MV3)](#2-browser-extension-chromeedge-mv3)
3. [FastAPI Backend Core](#3-fastapi-backend-core)
4. [ML & Detection Pipeline (Steps 3–6)](#4-ml--detection-pipeline-steps-36)
5. [User Moderation & Official PIB Escalation](#5-user-moderation--official-pib-escalation)
6. [Automated Test Suite & Verification](#6-automated-test-suite--verification)
7. [Implementation Progress Summary & Roadmap](#7-implementation-progress-summary--roadmap)

---

## 1. Monorepo & Infrastructure Architecture

The project is configured as a high-performance monorepo using **pnpm workspaces** and **Turborepo**:

* **Workspace Packages:**
  * `apps/extension`: Chrome & Edge Manifest V3 extension built with React, TypeScript, and Vite.
  * `apps/backend`: FastAPI web server, Celery async task queue, ML services, and database adapters.
  * `packages/types`: Centralized TypeScript package (`@truthlens/types`) ensuring compile-time type safety across frontend and backend API contracts.

* **Docker Infrastructure Stack (`docker/docker-compose.yml`):**
  * **PostgreSQL 16 with `pgvector`:** Vector database container for semantic similarity search over fact-check databases.
  * **Redis 7:** Low-latency caching layer for domain reputation results and Celery task broker.
  * **FastAPI Backend Container:** Main application container running Uvicorn with hot-reload support.
  * **Celery Worker Container:** Background task execution for resource-intensive asynchronous analysis (video and audio processing).

---

## 2. Browser Extension (Chrome/Edge MV3)

The extension provides non-intrusive, real-time feedback directly on news and media websites.

### Key Components Built:
* **Manifest V3 Core (`src/background/service-worker.ts`):**
  * Background service worker orchestrating tab events, side-panel communications, and badge updates.
  * Local state storage and background message routing.
* **Content Scripts:**
  * `extractor.ts`: Lightweight DOM parser extracting clean article body text, author metadata, publish timestamps, embedded images, and video nodes without uploading sensitive browsing history.
  * `highlighter.ts`: Non-destructive sentence and claim highlighter using the native CSS Custom Highlight API with `<mark>` element fallback.
    * 🟢 **Green (Verified):** Claims corroborated by reliable sources.
    * 🟡 **Yellow (Caution / Misleading):** Mixed context or unverified claims.
    * 🔴 **Red (Likely False):** Claims contradicted by established fact-check databases.
    * 🔘 **Gray (Unverified):** Insufficient data.
    * Includes interactive hover tooltips displaying claim explanations and source citations.
  * `shield.ts`: Active site-blocking script that intercepts blacklisted domains and displays a warning shield overlay.
  * `video-overlay.ts`: Media overlay badges injecting deepfake and AI-detection status indicators onto embedded video frames.
* **Popup & Side-Panel UI:**
  * Interactive **Credibility Score Gauge** (0–100 score band with explanations).
  * Tabbed interface for **Text Analysis**, **Media Deepfake Detection**, **Report/Block Modals**, and **Account Sync**.
  * Detailed claim breakdown list with direct links to publisher fact-checks (e.g., PolitiFact, Alt News, Snopes).

---

## 3. FastAPI Backend Core

The backend proxies all external API keys securely and hosts the multi-stage detection pipeline.

* **Application Entry Point (`apps/backend/app/main.py`):**
  * Configured CORS middleware supporting development extension origins (`chrome-extension://`).
  * GZip compression and request latency timing middleware (`X-TruthLens-Latency-Ms`).
  * Structured routes (`/api/analyze-text`, `/api/analyze-image`, `/api/analyze-video`, `/api/analyze-audio`, `/api/report`, `/api/block`, `/api/trending`, `/api/community`, `/api/auth`).
* **Pluggable Deepfake Adapter Architecture (`app/adapters/`):**
  * `base_deepfake.py`: Abstract interface defining uniform detection methods across media types.
  * `local_deepfake.py`: Open-source local model implementation (zero operational cost default).
  * `hive_deepfake.py`: Commercial API integration (Hive AI / Sensity) switchable via the `DEEPFAKE_PROVIDER` environment variable.

---

## 4. ML & Detection Pipeline (Steps 3–6)

```
Article Text
  │
  ├─► [Fast Pass: ~200ms]  DistilBERT ONNX Style Classifier
  │                        + Domain Reputation Database Lookup
  │                        ──► Instant visual badge update
  │
  └─► [Deep Analysis: 2–8s] Gemini LLM Claim Extraction
                           ──► Google Fact Check Tools API
                           ──► GDELT Global News Corpus
                           ──► pgvector Semantic Search
                           ──► Composite Scoring Model (50/20/15/15)
                           ──► Inline sentence highlighting & report breakdown
```

### Key Services Implemented:
1. **Gemini Claim Extractor (`app/services/claim_extractor.py`):**
   * Prompts Google Gemini LLM using structured JSON schema output.
   * Extracts distinct factual claims, context, and exact character offsets for inline DOM highlighting.
2. **Google Fact Check API (`app/services/fact_checker.py`):**
   * Queries verified fact-check publisher repositories for matching claim reviews.
3. **GDELT Global News Service (`app/services/gdelt_service.py`):**
   * Searches the GDELT Project API to measure international media corroboration and coverage volume.
4. **pgvector Semantic Search (`app/services/vector_search.py`):**
   * Performs vector similarity matching over previously verified claim embeddings.
5. **Composite Scoring Engine (`app/services/scorer.py`):**
   * Merges multiple signals into a weighted score (50% Fact Check API, 20% GDELT news, 15% Domain Reputation, 15% Vector Similarity).
6. **Result Synthesizer (`app/services/synthesizer.py`):**
   * Combines fast-pass writing style findings with deep claim extraction to output final verdict objects, confidence bands, and source citations.
7. **Writing Style & Clickbait Classifier (`app/services/style_classifier.py`):**
   * Fast DistilBERT ONNX classifier scanning for clickbait triggers, sensationalism, ALL-CAPS outrage indicators, and attribution patterns.
8. **Domain Reputation Engine (`app/services/domain_reputation.py`):**
   * Evaluates domain trust scores, satire flags (e.g., *The Onion*), and news reliability ratings.

---

## 5. User Moderation & Official PIB Escalation

* **User Reporting API (`routers/report.py` & `ReportModal.tsx`):**
  * Allows users to submit misinformation reports with category tagging (false information, clickbait, deepfake).
* **Official Press Information Bureau (PIB) Escalation:**
  * Automatically formats reports and generates direct escalation links for India's official **PIB Fact Check** unit:
    * 📱 **WhatsApp Direct Link:** Pre-filled message link to PIB (+91 8799711259).
    * ✉️ **Email Payload:** Pre-formatted email export (`pibfactcheck@gmail.com`).
    * 🌐 **Portal Link:** Direct link to `factcheck.pib.gov.in`.
* **Domain & Content Blocking (`routers/block.py` & `BlockModal.tsx`):**
  * Enables users to add domains or content patterns to a personal blocklist.
  * Synchronizes blocklists across extension instances and enforces active shield overlays.

---

## 6. Automated Test Suite & Verification

Unit and API tests implemented in `apps/backend/tests/`:
* `test_step3.py`: Validates claim extraction parsing and fact-check API mapping.
* `test_step5_services.py`: Tests domain reputation lookups, satire handling, clickbait scoring, and clean text classification.
* `test_step6_moderation.py`: Tests user report endpoints, PIB WhatsApp link generation, email payload export, and domain block/unblock state updates.

---

## 7. Implementation Progress Summary & Roadmap

| Step | Feature Description | Status |
|---|---|---|
| **Step 1** | Extension skeleton (MV3, service worker, extractor, popup) | ✅ Complete |
| **Step 2** | FastAPI backend scaffold & extension endpoint wiring | ✅ Complete |
| **Step 3** | Gemini claim extraction + Google Fact Check + GDELT API | ✅ Complete |
| **Step 4** | Composite credibility scoring engine & DOM highlighter synthesis | ✅ Complete |
| **Step 5** | Domain reputation database + DistilBERT fast-pass classifier | ✅ Complete |
| **Step 6** | User reporting system, site blocking + official PIB escalation | ✅ Complete |
| **Step 7** | React Native (Expo) mobile app scaffold & Share Sheet entry point | ⏳ Next |
| **Step 8** | AI-generated image detection & reverse image search pipeline | ⏳ Planned |
| **Step 9** | Deepfake video frame analyzer & audio voice clone detector | ⏳ Planned |
| **Step 10** | Supabase authentication & cross-device user sync | ⏳ Planned |
| **Step 11** | Community notes, bias compass, and trending misinformation feeds | ⏳ Planned |
| **Step 12** | Final UI/UX polish, production packaging, and demo script | ⏳ Planned |

---

*TruthLens v0.2.0 — Built step by step. Never 100% certain. Always cite sources.*
