-- V4: Alert schema — alerts raised when KQL rules match ES documents

CREATE TABLE alert.alerts (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text        NOT NULL,
    rule_id         uuid        NOT NULL REFERENCES policy.rules(id) ON DELETE RESTRICT,
    es_index        text        NOT NULL,
    es_document_id  text        NOT NULL,
    es_document_ts  timestamptz,
    severity        text        NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status          text        NOT NULL DEFAULT 'open'
                                CHECK (status IN ('open', 'in_review', 'closed')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (rule_id, es_document_id)
);

CREATE INDEX ON alert.alerts (rule_id);
CREATE INDEX ON alert.alerts (status);
CREATE INDEX ON alert.alerts (es_index, es_document_id);
CREATE INDEX ON alert.alerts (created_at DESC);
