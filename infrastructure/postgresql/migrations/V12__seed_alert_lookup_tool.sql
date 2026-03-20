-- V12: Seed alert_lookup tool and grant schema access for alert_lookup
-- The tool joins alert.alerts → policy.rules → policy.policies,
-- so both agent_rw and agent_readonly need read access to alert + policy schemas.

-- agent_rw (runtime role) needs alert + policy read access
GRANT USAGE ON SCHEMA alert TO agent_rw;
GRANT SELECT ON ALL TABLES IN SCHEMA alert TO agent_rw;
GRANT USAGE ON SCHEMA policy TO agent_rw;
GRANT SELECT ON ALL TABLES IN SCHEMA policy TO agent_rw;

-- agent_readonly also needs policy access (alert was already granted in V10)
GRANT USAGE ON SCHEMA policy TO agent_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA policy TO agent_readonly;

INSERT INTO agent.tools (name, display_name, description, category, parameters_schema)
VALUES (
    'alert_lookup',
    'Alert Lookup',
    'Look up alerts and their corresponding events. Joins alerts with rules and policies so you can filter by policy name, rule name, severity, status, or channel. Optionally fetches matching event documents from Elasticsearch.',
    'builtin',
    '{
        "type": "object",
        "properties": {
            "policy_name": {"type": "string", "description": "Filter by policy name (partial match)"},
            "rule_name": {"type": "string", "description": "Filter by rule name (partial match)"},
            "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
            "status": {"type": "string", "enum": ["open", "in_review", "closed"]},
            "channel": {"type": "string", "description": "Filter by channel (e.g. email, chat)"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            "fetch_events": {"type": "boolean", "default": true},
            "event_fields": {"type": "array", "items": {"type": "string"}}
        }
    }'::jsonb
)
ON CONFLICT (name) DO NOTHING;

-- Also seed the existing builtin tools if they don't exist yet
INSERT INTO agent.tools (name, display_name, description, category, parameters_schema)
VALUES
    ('es_search', 'ES Search', 'Full-text search and aggregation across Elasticsearch indices.', 'builtin', '{"type": "object", "properties": {"query": {"type": "string"}, "index": {"type": "string"}, "filters": {"type": "object"}, "fields": {"type": "array"}, "aggs": {"type": "object"}, "size": {"type": "integer"}}}'::jsonb),
    ('sql_query', 'SQL Query', 'Execute read-only SQL queries against PostgreSQL.', 'builtin', '{"type": "object", "properties": {"query": {"type": "string"}}}'::jsonb),
    ('es_get_mapping', 'ES Get Mapping', 'Retrieve Elasticsearch index field mapping.', 'builtin', '{"type": "object", "properties": {"index": {"type": "string"}}}'::jsonb)
ON CONFLICT (name) DO NOTHING;
