-- Hospital Intelligence: schema layout
--   raw      untransformed MIMIC-IV source tables (typed, values preserved)
--   meta     pipeline audit: runs, per-table load stats, rejects, profiles, checks
--   staging / intermediate / marts / reporting are created and owned by dbt
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS meta;

CREATE TABLE IF NOT EXISTS meta.ingestion_runs (
    run_id          bigserial PRIMARY KEY,
    dataset_label   text        NOT NULL,
    dataset_mode    text        NOT NULL CHECK (dataset_mode IN ('demo', 'full')),
    started_at      timestamptz NOT NULL DEFAULT now(),
    finished_at     timestamptz,
    status          text        NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'succeeded', 'failed', 'partial')),
    notes           text
);

-- One row per table per run. Skipped (unchanged) tables are recorded too,
-- which makes restarts auditable.
CREATE TABLE IF NOT EXISTS meta.ingestion_table_log (
    run_id              bigint      NOT NULL REFERENCES meta.ingestion_runs (run_id),
    table_name          text        NOT NULL,
    source_file         text        NOT NULL,
    file_sha256         text,
    contract_hash       text,
    status              text        NOT NULL
                        CHECK (status IN ('loaded', 'skipped_unchanged', 'skipped_missing', 'failed')),
    source_rows         bigint,
    loaded_rows         bigint,
    rejected_rows       bigint,
    duplicate_key_rows  bigint,
    orphan_rows         jsonb,
    extra_columns       text[],
    duration_seconds    numeric(12, 3),
    error_message       text,
    logged_at           timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, table_name)
);

-- Rows that failed type parsing or NOT NULL rules. The original record is
-- preserved as text so it can be investigated. Patient-level: never exported.
CREATE TABLE IF NOT EXISTS meta.rejected_rows (
    run_id          bigint  NOT NULL,
    table_name      text    NOT NULL,
    source_line     bigint  NOT NULL,
    reason          text    NOT NULL,
    raw_record      jsonb   NOT NULL
);

CREATE TABLE IF NOT EXISTS meta.column_profile (
    run_id          bigint  NOT NULL,
    table_name      text    NOT NULL,
    column_name     text    NOT NULL,
    row_count       bigint  NOT NULL,
    null_count      bigint  NOT NULL,
    null_pct        numeric(7, 3) NOT NULL,
    sampled         boolean NOT NULL DEFAULT false,
    PRIMARY KEY (run_id, table_name, column_name)
);

-- Post-load plausibility checks. Suspicious records are flagged, never deleted.
CREATE TABLE IF NOT EXISTS meta.validation_results (
    run_id          bigint  NOT NULL,
    check_name      text    NOT NULL,
    table_name      text    NOT NULL,
    severity        text    NOT NULL CHECK (severity IN ('error', 'warn', 'info')),
    status          text    NOT NULL CHECK (status IN ('pass', 'flag', 'fail')),
    flagged_rows    bigint  NOT NULL,
    description     text    NOT NULL,
    checked_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, check_name)
);

-- SQL benchmark results (written by analytics/performance/benchmark.py)
CREATE TABLE IF NOT EXISTS meta.query_benchmarks (
    benchmark_id    bigserial PRIMARY KEY,
    benchmarked_at  timestamptz NOT NULL DEFAULT now(),
    dataset_label   text    NOT NULL,
    case_name       text    NOT NULL,
    variant         text    NOT NULL CHECK (variant IN ('baseline', 'optimized')),
    runs            int     NOT NULL,
    median_ms       numeric(12, 3) NOT NULL,
    min_ms          numeric(12, 3) NOT NULL,
    max_ms          numeric(12, 3) NOT NULL,
    result_hash     text    NOT NULL,
    result_rows     bigint  NOT NULL
);
