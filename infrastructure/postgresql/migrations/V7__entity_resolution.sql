-- V7: Entity resolution — entities, handles, attributes

CREATE SCHEMA IF NOT EXISTS entity;

-- Entities: people, organizations, distribution lists
CREATE TABLE entity.entities (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name  text        NOT NULL,
    entity_type   text        NOT NULL,  -- 'person', 'organization', 'distribution_list'
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    created_by    uuid        REFERENCES iam.users(id),
    UNIQUE (display_name, entity_type)
);

CREATE INDEX ON entity.entities (entity_type);

-- Handles: map channel-specific identifiers to entities
CREATE TABLE entity.handles (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id     uuid        NOT NULL REFERENCES entity.entities(id) ON DELETE CASCADE,
    handle_type   text        NOT NULL,  -- 'email', 'teams_id', 'bloomberg_uuid', 'turret_extension'
    handle_value  text        NOT NULL,  -- normalized (lowercased for email)
    is_primary    boolean     NOT NULL DEFAULT false,
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (handle_type, handle_value)
);

CREATE INDEX ON entity.handles (entity_id);

-- Attributes: extensible key-value pairs with optional temporal validity
CREATE TABLE entity.attributes (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id     uuid        NOT NULL REFERENCES entity.entities(id) ON DELETE CASCADE,
    attr_key      text        NOT NULL,
    attr_value    text        NOT NULL,
    valid_from    timestamptz,
    valid_to      timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (entity_id, attr_key, valid_from)
);

CREATE INDEX ON entity.attributes (entity_id);
