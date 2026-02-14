-- V2: IAM schema — users, groups, roles, RBAC

CREATE TABLE iam.users (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    username      text        UNIQUE NOT NULL,
    email         text        UNIQUE NOT NULL,
    password_hash text        NOT NULL,
    is_active     boolean     NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE iam.roles (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text        UNIQUE NOT NULL,
    description text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE iam.groups (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text        UNIQUE NOT NULL,
    description text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE iam.user_groups (
    user_id     uuid        NOT NULL REFERENCES iam.users(id)  ON DELETE CASCADE,
    group_id    uuid        NOT NULL REFERENCES iam.groups(id) ON DELETE CASCADE,
    assigned_by uuid        REFERENCES iam.users(id),
    assigned_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, group_id)
);

CREATE TABLE iam.group_roles (
    group_id    uuid        NOT NULL REFERENCES iam.groups(id) ON DELETE CASCADE,
    role_id     uuid        NOT NULL REFERENCES iam.roles(id)  ON DELETE CASCADE,
    assigned_by uuid        REFERENCES iam.users(id),
    assigned_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (group_id, role_id)
);

-- Index for the role-lookup join: users → user_groups → group_roles → roles
CREATE INDEX ON iam.user_groups (group_id);
CREATE INDEX ON iam.group_roles (role_id);
