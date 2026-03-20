-- V10: Agent layer — models, tools, agents, runs, run_steps

CREATE SCHEMA IF NOT EXISTS agent;

-- Registered LLM endpoints
CREATE TABLE agent.models (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text        UNIQUE NOT NULL,
    provider        text        NOT NULL,
    model_id        text        NOT NULL,
    base_url        text,
    api_key_secret  text,
    max_tokens      int         NOT NULL DEFAULT 4096,
    is_active       boolean     NOT NULL DEFAULT true,
    created_by      uuid        REFERENCES iam.users(id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- Tool registry
CREATE TABLE agent.tools (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name              text        UNIQUE NOT NULL,
    display_name      text        NOT NULL,
    description       text        NOT NULL,
    category          text        NOT NULL CHECK (category IN ('builtin', 'custom')),
    parameters_schema jsonb       NOT NULL,
    is_active         boolean     NOT NULL DEFAULT true,
    created_at        timestamptz NOT NULL DEFAULT now()
);

-- Agent definitions
CREATE TABLE agent.agents (
    id              uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text          NOT NULL,
    description     text,
    model_id        uuid          NOT NULL REFERENCES agent.models(id) ON DELETE RESTRICT,
    system_prompt   text          NOT NULL,
    temperature     numeric(3,2)  NOT NULL DEFAULT 0.0,
    max_iterations  int           NOT NULL DEFAULT 10,
    output_schema   jsonb,
    is_builtin      boolean       NOT NULL DEFAULT false,
    is_active       boolean       NOT NULL DEFAULT true,
    created_by      uuid          REFERENCES iam.users(id),
    created_at      timestamptz   NOT NULL DEFAULT now(),
    updated_at      timestamptz   NOT NULL DEFAULT now(),
    UNIQUE (name, created_by)
);

CREATE INDEX ON agent.agents (model_id);
CREATE INDEX ON agent.agents (created_by);

-- Many-to-many: agent ↔ tools
CREATE TABLE agent.agent_tools (
    agent_id    uuid    NOT NULL REFERENCES agent.agents(id) ON DELETE CASCADE,
    tool_id     uuid    NOT NULL REFERENCES agent.tools(id)  ON DELETE CASCADE,
    tool_config jsonb,
    PRIMARY KEY (agent_id, tool_id)
);

CREATE INDEX ON agent.agent_tools (tool_id);

-- Data source access control per agent
CREATE TABLE agent.agent_data_sources (
    id                uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id          uuid    NOT NULL REFERENCES agent.agents(id) ON DELETE CASCADE,
    source_type       text    NOT NULL CHECK (source_type IN ('elasticsearch', 'postgresql')),
    source_identifier text    NOT NULL,
    access_mode       text    NOT NULL DEFAULT 'read' CHECK (access_mode IN ('read')),
    UNIQUE (agent_id, source_type, source_identifier)
);

CREATE INDEX ON agent.agent_data_sources (agent_id);

-- Execution log
CREATE TABLE agent.runs (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id      uuid        NOT NULL REFERENCES agent.agents(id) ON DELETE RESTRICT,
    status        text        NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    input         jsonb       NOT NULL,
    output        jsonb,
    error_message text,
    token_usage   jsonb,
    iterations    int,
    duration_ms   int,
    triggered_by  uuid        NOT NULL REFERENCES iam.users(id),
    created_at    timestamptz NOT NULL DEFAULT now(),
    completed_at  timestamptz
);

CREATE INDEX ON agent.runs (agent_id);
CREATE INDEX ON agent.runs (triggered_by);
CREATE INDEX ON agent.runs (created_at DESC);
CREATE INDEX ON agent.runs (status);

-- Step trace within a run
CREATE TABLE agent.run_steps (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id      uuid        NOT NULL REFERENCES agent.runs(id) ON DELETE CASCADE,
    step_order  int         NOT NULL,
    step_type   text        NOT NULL CHECK (step_type IN ('llm_call', 'tool_call', 'tool_result')),
    tool_name   text,
    input       jsonb       NOT NULL,
    output      jsonb,
    token_usage jsonb,
    duration_ms int,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ON agent.run_steps (run_id, step_order);

-- Roles
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_rw') THEN
        CREATE ROLE agent_rw WITH LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_readonly') THEN
        CREATE ROLE agent_readonly WITH LOGIN;
    END IF;
END
$$;

-- agent_rw: full access to agent schema, read access to iam and entity
GRANT USAGE ON SCHEMA agent TO agent_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA agent TO agent_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA agent GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO agent_rw;

GRANT USAGE ON SCHEMA iam TO agent_rw;
GRANT SELECT ON ALL TABLES IN SCHEMA iam TO agent_rw;

GRANT USAGE ON SCHEMA entity TO agent_rw;
GRANT SELECT ON ALL TABLES IN SCHEMA entity TO agent_rw;

-- agent_readonly: SELECT only on agent schema (used by SQL tool)
GRANT USAGE ON SCHEMA agent TO agent_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA agent TO agent_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA agent GRANT SELECT ON TABLES TO agent_readonly;

GRANT USAGE ON SCHEMA iam TO agent_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA iam TO agent_readonly;

GRANT USAGE ON SCHEMA entity TO agent_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA entity TO agent_readonly;

GRANT USAGE ON SCHEMA alert TO agent_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA alert TO agent_readonly;

GRANT USAGE ON SCHEMA review TO agent_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA review TO agent_readonly;
