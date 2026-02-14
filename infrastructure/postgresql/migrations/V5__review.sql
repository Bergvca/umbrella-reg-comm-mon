-- V5: Review schema — queues, batches, items, decision statuses, decisions, audit log

CREATE TABLE review.queues (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text        NOT NULL,
    description text,
    policy_id   uuid        NOT NULL REFERENCES policy.policies(id) ON DELETE RESTRICT,
    created_by  uuid        REFERENCES iam.users(id),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE review.queue_batches (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_id    uuid        NOT NULL REFERENCES review.queues(id) ON DELETE CASCADE,
    name        text,
    assigned_to uuid        REFERENCES iam.users(id) ON DELETE SET NULL,
    assigned_by uuid        REFERENCES iam.users(id) ON DELETE SET NULL,
    assigned_at timestamptz,
    status      text        NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'in_progress', 'completed')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE review.queue_items (
    id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id   uuid        NOT NULL REFERENCES review.queue_batches(id) ON DELETE CASCADE,
    alert_id   uuid        NOT NULL REFERENCES alert.alerts(id)         ON DELETE RESTRICT,
    position   int         NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (batch_id, alert_id),
    UNIQUE (batch_id, position)
);

CREATE TABLE review.decision_statuses (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name          text        UNIQUE NOT NULL,
    description   text,
    is_terminal   boolean     NOT NULL DEFAULT false,
    display_order int         NOT NULL DEFAULT 0,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE review.decisions (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id    uuid        NOT NULL REFERENCES alert.alerts(id)                ON DELETE RESTRICT,
    reviewer_id uuid        NOT NULL REFERENCES iam.users(id)                  ON DELETE RESTRICT,
    status_id   uuid        NOT NULL REFERENCES review.decision_statuses(id)   ON DELETE RESTRICT,
    comment     text,
    decided_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE review.audit_log (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id uuid        NOT NULL REFERENCES review.decisions(id) ON DELETE CASCADE,
    actor_id    uuid        REFERENCES iam.users(id),
    action      text        NOT NULL CHECK (action IN ('created', 'updated', 'deleted')),
    old_values  jsonb,
    new_values  jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    ip_address  inet,
    user_agent  text
);

-- Indexes
CREATE INDEX ON review.queue_batches (queue_id);
CREATE INDEX ON review.queue_batches (assigned_to);
CREATE INDEX ON review.queue_items   (batch_id);
CREATE INDEX ON review.queue_items   (alert_id);
CREATE INDEX ON review.decisions     (alert_id);
CREATE INDEX ON review.decisions     (reviewer_id);
CREATE INDEX ON review.audit_log     (decision_id);
CREATE INDEX ON review.audit_log     (actor_id);
CREATE INDEX ON review.audit_log     (occurred_at DESC);

-- Trigger: prevent UPDATE or DELETE on audit_log (append-only)
CREATE OR REPLACE FUNCTION review.audit_log_immutable()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log rows are immutable';
END;
$$;

CREATE TRIGGER audit_log_no_update
    BEFORE UPDATE ON review.audit_log
    FOR EACH ROW EXECUTE FUNCTION review.audit_log_immutable();

CREATE TRIGGER audit_log_no_delete
    BEFORE DELETE ON review.audit_log
    FOR EACH ROW EXECUTE FUNCTION review.audit_log_immutable();
