-- V3: Policy schema — risk models, policies, rules, group assignments

CREATE TABLE policy.risk_models (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text        UNIQUE NOT NULL,
    description text,
    is_active   boolean     NOT NULL DEFAULT true,
    created_by  uuid        REFERENCES iam.users(id),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE policy.policies (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    risk_model_id uuid        NOT NULL REFERENCES policy.risk_models(id) ON DELETE RESTRICT,
    name          text        NOT NULL,
    description   text,
    is_active     boolean     NOT NULL DEFAULT true,
    created_by    uuid        REFERENCES iam.users(id),
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (risk_model_id, name)
);

CREATE TABLE policy.rules (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id   uuid        NOT NULL REFERENCES policy.policies(id) ON DELETE CASCADE,
    name        text        NOT NULL,
    description text,
    kql         text        NOT NULL,
    severity    text        NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    is_active   boolean     NOT NULL DEFAULT true,
    created_by  uuid        REFERENCES iam.users(id),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE policy.group_policies (
    group_id    uuid        NOT NULL REFERENCES iam.groups(id)      ON DELETE CASCADE,
    policy_id   uuid        NOT NULL REFERENCES policy.policies(id) ON DELETE CASCADE,
    assigned_by uuid        REFERENCES iam.users(id),
    assigned_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (group_id, policy_id)
);

CREATE INDEX ON policy.policies (risk_model_id);
CREATE INDEX ON policy.rules    (policy_id);
CREATE INDEX ON policy.group_policies (policy_id);
