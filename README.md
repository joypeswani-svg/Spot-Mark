# TruthLens

Real-time fake news, deepfake, and AI-image detection across three surfaces — sharing one backend and one ML pipeline.

| Surface | Status |
|---|---|
| 🌐 Browser Extension (Chrome/Edge MV3) | **Step 2 — wired to backend** |
| 📱 Mobile App (React Native + Expo) | Step 7 |
| ⚙️ FastAPI Backend + ML Pipeline | Step 2 stubs wired, Step 3 next |

---

## Quick Start

### Prerequisites

| Tool | Version | Install |
|---|---|---|
| Node.js | ≥ 20 | [nodejs.org](https://nodejs.org) |
| pnpm | ≥ 9 | `npm i -g pnpm` |
| Docker Desktop | Latest | [docker.com](https://docker.com) |
| Python | 3.11+ | [python.org](https://python.org) |

---

### 1. Clone & Install

```bash
git clone https://github.com/Muneeb7Siddiqui/Spot-Mark.git
cd Spot-Mark
pnpm install
```

### 2. Start the Backend Stack

```bash
# Start Postgres + Redis (Docker)
cd docker
docker compose up -d

# Set up backend environment
cd ../apps/backend
cp .env.example .env
# Edit .env and add your API keys (see section below)

# Install Python dependencies
pip install -r requirements.txt

# Start the FastAPI server (dev mode with hot reload)
uvicorn app.main:app --reload
# → API running at http://localhost:8000
# → Docs at http://localhost:8000/docs
```

### 3. Build the Extension

```bash
cd apps/extension
pnpm build          # production build → dist/
# OR
pnpm dev            # watch mode for development
```

### 4. Load the Extension in Chrome/Edge

1. Open `chrome://extensions` (or `edge://extensions`)
2. Enable **Developer mode** (top right toggle)
3. Click **Load unpacked**
4. Select the `apps/extension/dist/` folder
5. Navigate to any news article — the TruthLens icon appears in the toolbar

---

## API Keys Setup

All keys go in `apps/backend/.env` (copy from `.env.example`). **API keys never go in the extension or mobile app bundle.**

| Key | Required | Free? | Get it at |
|---|---|---|---|
| `GEMINI_API_KEY` | Step 3+ | ✅ Free tier | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| `GOOGLE_FACT_CHECK_API_KEY` | Step 3+ | ✅ Free | [Google Console](https://developers.google.com/fact-check/tools/api) |
| `GOOGLE_VISION_API_KEY` | Step 8+ | ✅ 1k/mo free | [Google Console](https://console.cloud.google.com) |
| `SUPABASE_URL` + `SUPABASE_ANON_KEY` | Step 10 | ✅ Free tier | [supabase.com](https://supabase.com) |
| `HIVE_API_KEY` | Optional | ❌ Paid | [thehive.ai](https://thehive.ai) |
| `SENSITY_API_KEY` | Optional | ❌ Paid | [sensity.ai](https://sensity.ai) |

---

## Monorepo Structure

```
truthlens/
├── apps/
│   ├── extension/          Chrome/Edge MV3 extension (React + TypeScript)
│   ├── mobile/             React Native (Expo) iOS + Android app
│   └── backend/            FastAPI + Celery + ML pipeline
├── packages/
│   ├── types/              Shared TypeScript types (@truthlens/types)
│   └── ui-tokens/          Shared design tokens
├── docker/
│   ├── docker-compose.yml  Postgres + Redis + Backend
│   └── postgres/init.sql   pgvector schema bootstrap
└── docs/
    ├── architecture.md
    └── demo-script.md
```

---

## Architecture

```
┌──────────────────────┐    ┌─────────────────────────────────┐
│   Chrome Extension   │    │        React Native App          │
│   (Popup + Content   │    │  (Share Sheet → Result Screen)   │
│    Scripts + SW)     │    │                                  │
└──────────┬───────────┘    └────────────────┬────────────────┘
           │  HTTPS + Supabase JWT           │
           └─────────────┬──────────────────┘
                         ▼
          ┌──────────────────────────────┐
          │       FastAPI Backend        │
          │  /api/analyze-text           │
          │  /api/analyze-image          │
          │  /api/analyze-video (async)  │
          │  /api/analyze-audio (async)  │
          │  /api/report  /api/block     │
          └────────────┬─────────────────┘
                       │
          ┌────────────┼──────────────┐
          ▼            ▼              ▼
    ┌──────────┐  ┌─────────┐  ┌──────────┐
    │ Postgres │  │  Redis  │  │  Celery  │
    │+pgvector │  │  Cache  │  │ Workers  │
    └──────────┘  └─────────┘  └──────────┘
```

### Detection Pipeline (Step 3+)

```
Article Text
    │
    ├─→ [Fast, ~200ms] DistilBERT ONNX style classifier
    │                  + Domain reputation CSV lookup
    │                  → Immediate badge update
    │
    └─→ [Deep, 2–10s] Gemini LLM claim extraction (structured JSON)
                       → Google Fact Check Tools API (per claim)
                       → GDELT Project API (corroboration)
                       → pgvector similarity search (fact corpus)
                       → Composite score (50/20/15/15 weights)
                       → Badge update + inline highlighting
```

### Credibility Score

| Score | Band | Color | Meaning |
|---|---|---|---|
| 80–100 | Verified | 🟢 Green | Claims corroborated by credible sources |
| 50–79 | Caution | 🟡 Yellow | Mixed or insufficient corroboration |
| 0–49 | Likely False | 🔴 Red | Claims contradicted by credible sources |
| — | Unverified | ⚫ Gray | Could not reach analysis service |

**Never shows 100% certainty. Always shows explanation + sources. Never a bare number.**

---

## Step-by-Step Build Progress

| Step | Description | Status |
|---|---|---|
| 1 | Extension skeleton — manifest, service worker, extractor, popup | ✅ Complete |
| 2 | FastAPI stub backend wired to extension popup | ✅ Complete |
| 3 | Real claim extraction (Gemini) + Fact Check + GDELT | ✅ Complete |
| 4 | Scoring model + badge + inline highlighter | ✅ Complete |
| 5 | Domain reputation + DistilBERT fast-pass | ⏳ |
| 6 | Report & Block feature (separate flows, deep-links) | ⏳ |
| 7 | Mobile app scaffold (Expo, share-sheet entry point) | ⏳ |
| 8 | AI-image detection + reverse image search | ⏳ |
| 9 | Deepfake video + voice clone detection (pluggable) | ⏳ |
| 10 | Account system + cross-device sync (Supabase) | ⏳ |
| 11 | Remaining features: bias compass, community notes, OCR, trending | ⏳ |
| 12 | Polish UI/UX, README, demo script | ⏳ |

---

## Non-Negotiables (Design Constraints)

- 🔐 **API keys never in client bundles** — all model/API calls proxied through backend
- 🎯 **Never claim 100% certainty** — always show confidence range + cited sources
- 🚫 **Never silently modify page content** — overlay/annotate only
- 🔀 **Report ≠ Block** — always two clearly separate actions/screens/endpoints
- 🔌 **Deepfake provider is pluggable** — local model default, paid API as labeled optional upgrade
- 🛡️ **Graceful API failure** — show "couldn't verify" on any error, never a false verdict
- 🕵️ **Privacy-first** — no full browsing history sent without opt-in

---

## Development Commands

```bash
# Monorepo root
pnpm build          # Build all packages
pnpm dev            # Start all dev servers

# Extension only
pnpm --filter @truthlens/extension build
pnpm --filter @truthlens/extension dev

# Backend
uvicorn app.main:app --reload               # FastAPI dev server
celery -A app.tasks.celery_app worker -l info  # Celery worker

# Docker
docker compose -f docker/docker-compose.yml up -d   # Start infra
docker compose -f docker/docker-compose.yml down    # Stop infra
docker compose -f docker/docker-compose.yml logs -f backend  # Logs
```

---

## Contributing

This is a monorepo using pnpm workspaces + Turborepo. All shared types go in `packages/types/`. Never add API keys to any client-side code.

---

*TruthLens v0.1 — Built step by step. Never 100% certain. Always cite sources.*
