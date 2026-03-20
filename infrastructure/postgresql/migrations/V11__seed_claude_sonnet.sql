-- V11: Seed Claude Sonnet 4.6 model (via OpenRouter) and a default agent

INSERT INTO agent.models (name, provider, model_id, base_url, api_key_secret, max_tokens)
VALUES (
    'Claude Sonnet 4.6 (OpenRouter)',
    'openrouter',
    'anthropic/claude-sonnet-4-6',
    'https://openrouter.ai/api/v1',
    'REPLACE_WITH_OPENROUTER_API_KEY',
    8192
)
ON CONFLICT (name) DO NOTHING;

INSERT INTO agent.agents (name, description, model_id, system_prompt, temperature, max_iterations, is_builtin)
SELECT
    'Claude Sonnet 4.6',
    'General-purpose compliance and communications analytics agent powered by Claude Sonnet 4.6 via OpenRouter.',
    m.id,
    'You are an expert compliance and communications analytics assistant. You have access to tools that query Elasticsearch indexes containing normalized communications data (emails, chats, calls, etc.) and a PostgreSQL database containing policy, alert, and entity data.

When asked to investigate or analyse:
1. Start by searching for relevant messages using the search tools.
2. Cross-reference with entity and policy data where appropriate.
3. Summarise findings clearly and concisely, citing specific evidence.
4. Flag any patterns or anomalies that may indicate a compliance concern.

Always ground your answers in the data returned by your tools — do not speculate beyond what the data shows.',
    0.0,
    10,
    true
FROM agent.models m
WHERE m.name = 'Claude Sonnet 4.6 (OpenRouter)'
ON CONFLICT DO NOTHING;
