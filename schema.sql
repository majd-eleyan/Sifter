-- =========================================================
-- Database design: 3 tables
--   documents        one CV = one row (plus its metadata)
--   document_chunks  CV chunks + their embeddings
--   rag_traces       a log of every question (tracing for evaluation)
-- =========================================================
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id                BIGSERIAL PRIMARY KEY,
    filename          TEXT NOT NULL UNIQUE,
    drive_file_id     TEXT UNIQUE,                       -- Google Drive file id (NULL if not from Drive)
    candidate_name    TEXT,
    title             TEXT,                              -- job title
    department        TEXT,
    years_experience  NUMERIC(4,1),
    skills            TEXT[] NOT NULL DEFAULT '{}',
    full_text         TEXT NOT NULL,                     -- the whole CV text (this is what we send to the LLM)
    ats_ok            BOOLEAN NOT NULL DEFAULT FALSE,
    ats_issues        TEXT[] NOT NULL DEFAULT '{}',
    status            VARCHAR(20) NOT NULL DEFAULT 'pending_review'
                      CHECK (status IN ('ready', 'pending_review', 'rejected')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id           BIGSERIAL PRIMARY KEY,
    document_id  BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    strategy     TEXT NOT NULL DEFAULT 'section',        -- section | recursive | fixed
    chunk_index  INT NOT NULL,
    section      TEXT,
    content      TEXT NOT NULL,
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding    VECTOR(384),
    UNIQUE (document_id, strategy, chunk_index)
);

-- HNSW index for fast vector search (the ANN idea from the session notes).
-- With 15 CVs it is not needed, but it keeps search fast when the data grows.
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks (document_id);

CREATE TABLE IF NOT EXISTS rag_traces (
    id                 BIGSERIAL PRIMARY KEY,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    test_id            TEXT,                             -- evaluation test case id
    prompt_version     TEXT,
    question           TEXT NOT NULL,
    retrieved          JSONB,                            -- chunks that were retrieved
    sent_cvs           JSONB,                            -- CVs that were sent to the LLM
    answer             TEXT,
    error              TEXT,
    retrieval_ms       INT,
    llm_ms             INT,
    total_ms           INT,
    prompt_tokens      INT,
    completion_tokens  INT,
    cost_usd           NUMERIC(10,6)
);
