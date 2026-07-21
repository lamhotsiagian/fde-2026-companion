-- Guardrails migration: audit trail, rate limiting, semantic dedup, centroids.
-- Idempotent; safe to run on an existing database.

CREATE EXTENSION IF NOT EXISTS vector;

-- L9: every guard verdict, keyed by tenant like all other tables.
CREATE TABLE IF NOT EXISTS guard_audit (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID,
    session_id  TEXT,
    thread_id   TEXT,
    layer       TEXT NOT NULL,
    verdict     JSONB NOT NULL,
    latency_ms  DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_guard_audit_tenant_time
    ON guard_audit (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_guard_audit_layer
    ON guard_audit (layer, created_at DESC);

-- L7: sliding-window rate limiting (swap for Redis at scale).
CREATE TABLE IF NOT EXISTS rate_events (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_rate_events_tenant_time
    ON rate_events (tenant_id, created_at DESC);

-- L4: per-session answer embeddings for semantic dedup.
CREATE TABLE IF NOT EXISTS session_answers (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL,
    session_id  TEXT NOT NULL,
    embedding   VECTOR(768) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_session_answers_keys
    ON session_answers (tenant_id, session_id);
CREATE INDEX IF NOT EXISTS ix_session_answers_hnsw
    ON session_answers USING hnsw (embedding vector_cosine_ops);

-- L3/L4: one centroid per course chapter, computed from chapter summaries.
CREATE TABLE IF NOT EXISTS chapter_centroids (
    chapter     INT PRIMARY KEY,
    title       TEXT NOT NULL,
    embedding   VECTOR(768) NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_chapter_centroids_hnsw
    ON chapter_centroids USING hnsw (embedding vector_cosine_ops);

-- Retention: rate events are useless after an hour; keep audit 90 days.
-- Run from a cron/pg_cron job:
--   DELETE FROM rate_events WHERE created_at < now() - interval '1 hour';
--   DELETE FROM guard_audit WHERE created_at < now() - interval '90 days';
