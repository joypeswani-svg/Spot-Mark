-- TruthLens PostgreSQL Bootstrap
-- Runs once when the Docker container is first initialized.
-- Extensions and core schema are created here; Alembic manages migrations after.

-- ── Extensions ──────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";          -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS "pg_trgm";         -- trigram similarity for text search
CREATE EXTENSION IF NOT EXISTS "btree_gin";       -- GIN index support

-- ── Core Tables ──────────────────────────────────────────────────────────────

-- Cached analysis results (deduped by URL hash)
CREATE TABLE IF NOT EXISTS analysis_cache (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url_hash        TEXT NOT NULL UNIQUE,       -- SHA256 of normalized URL
    url             TEXT NOT NULL,
    title           TEXT,
    result_json     JSONB NOT NULL,             -- Full AnalyzeTextResponse JSON
    credibility_score INTEGER NOT NULL,         -- 0–100, for quick filtering
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours'
);
CREATE INDEX IF NOT EXISTS idx_analysis_cache_url_hash ON analysis_cache (url_hash);
CREATE INDEX IF NOT EXISTS idx_analysis_cache_expires_at ON analysis_cache (expires_at);

-- Fact-checked corpus embeddings (Snopes, PolitiFact, Reuters, etc.)
CREATE TABLE IF NOT EXISTS corpus_embeddings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    claim_text      TEXT NOT NULL,
    verdict         TEXT NOT NULL CHECK (verdict IN ('TRUE','FALSE','MISLEADING','UNVERIFIED')),
    explanation     TEXT,
    source_url      TEXT,
    source_name     TEXT,
    published_at    TIMESTAMPTZ,
    -- 384-dim embedding from sentence-transformers all-MiniLM-L6-v2
    embedding       VECTOR(384),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- IVFFlat index for approximate nearest-neighbor search
-- (rebuild after inserting significant corpus data: CREATE INDEX ...)
CREATE INDEX IF NOT EXISTS idx_corpus_embeddings_vec
    ON corpus_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- User accounts (synced from Supabase Auth)
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY,           -- matches Supabase auth.users.id
    email           TEXT UNIQUE,
    display_name    TEXT,
    truth_score     INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Block lists (synced across devices)
CREATE TABLE IF NOT EXISTS block_list_entries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target          TEXT NOT NULL,              -- domain, account handle, or channel URL
    target_type     TEXT NOT NULL CHECK (target_type IN ('domain','account','channel')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, target, target_type)
);
CREATE INDEX IF NOT EXISTS idx_block_list_user ON block_list_entries (user_id);

-- Community notes
CREATE TABLE IF NOT EXISTS community_notes (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_url         TEXT NOT NULL,
    note_text           TEXT NOT NULL,
    verdict             TEXT NOT NULL,
    author_id           UUID REFERENCES users(id),
    contributor_rep     INTEGER NOT NULL DEFAULT 50,
    upvotes             INTEGER NOT NULL DEFAULT 0,
    downvotes           INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_community_notes_url ON community_notes (content_url);

-- Trending flags
CREATE TABLE IF NOT EXISTS trending_flags (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    headline        TEXT NOT NULL,
    claim_text      TEXT NOT NULL,
    verdict         TEXT NOT NULL,
    credibility_score INTEGER NOT NULL,
    share_count     INTEGER NOT NULL DEFAULT 0,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_trending_flags_share_count ON trending_flags (share_count DESC);

-- Personal truth score events (for gamified analytics dashboard)
CREATE TABLE IF NOT EXISTS truth_score_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,              -- e.g. 'verified_true', 'shared_flagged'
    url             TEXT,
    points          INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_truth_score_events_user ON truth_score_events (user_id, created_at DESC);

-- ── Helper function: cleanup expired cache ───────────────────────────────────

CREATE OR REPLACE FUNCTION cleanup_expired_cache() RETURNS void AS $$
BEGIN
    DELETE FROM analysis_cache WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- ── Seed data placeholder ────────────────────────────────────────────────────
-- Full corpus loading is done by the backend startup script (Step 3).
