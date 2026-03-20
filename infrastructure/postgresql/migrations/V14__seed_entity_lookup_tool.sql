INSERT INTO agent.tools (name, display_name, description, category, parameters_schema)
VALUES (
    'entity_lookup',
    'Entity Lookup',
    'Look up entities by name, handle, type, or attributes. Can include alert counts.',
    'builtin',
    '{"type": "object", "properties": {"entity_name": {"type": "string", "description": "Search by display name (partial match)"}, "entity_type": {"type": "string", "enum": ["person", "organization", "distribution_list"]}, "handle_value": {"type": "string", "description": "Exact match on handle value"}, "attr_key": {"type": "string", "description": "Filter by attribute key"}, "attr_value": {"type": "string", "description": "Filter by attribute value (partial match)"}, "include_alerts": {"type": "boolean", "default": false}, "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}}}'::jsonb
)
ON CONFLICT (name) DO NOTHING;
