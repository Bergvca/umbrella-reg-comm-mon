-- V8: alert generation jobs table

CREATE TABLE alert.generation_jobs (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type          TEXT        NOT NULL CHECK (scope_type IN ('all', 'policies', 'risk_models')),
    scope_ids           UUID[],
    query_kql           TEXT,
    query_kql_resolved  TEXT,
    status              TEXT        NOT NULL DEFAULT 'pending'
                                    CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    alerts_created      INTEGER     NOT NULL DEFAULT 0,
    rules_evaluated     INTEGER     NOT NULL DEFAULT 0,
    documents_scanned   BIGINT      NOT NULL DEFAULT 0,
    error_message       TEXT,
    created_by          UUID        NOT NULL REFERENCES iam.users(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    schedule_cron       TEXT,
    schedule_active     BOOLEAN     NOT NULL DEFAULT false
);

CREATE INDEX ON alert.generation_jobs (created_at DESC);
CREATE INDEX ON alert.generation_jobs (status);
