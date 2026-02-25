"""Agent execution engine — builds and runs LangGraph ReAct agents."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

import structlog
from elasticsearch import AsyncElasticsearch
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from litellm import acompletion
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from umbrella_agents.callbacks.audit import AuditCallbackHandler
from umbrella_agents.db.models import Agent, AgentDataSource, Run
from umbrella_agents.tools.registry import DataSourceScope, get_registry

logger = structlog.get_logger()


class _LiteLLMChatModel:
    """Minimal LangChain-compatible chat model wrapper around LiteLLM.

    LangGraph's ``create_react_agent`` needs a model that supports
    ``.bind_tools()`` and ``ainvoke(messages)``.  This thin wrapper
    delegates to LiteLLM ``acompletion`` so we stay model-agnostic.
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = api_key
        self.base_url = base_url
        self._bound_tools: list[dict] | None = None

    def bind_tools(self, tools: list, **kwargs):
        """Return a copy of self with tools bound (for LangGraph)."""
        clone = _LiteLLMChatModel(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            api_key=self.api_key,
            base_url=self.base_url,
        )
        # Convert LangChain tools to OpenAI-style function schemas
        tool_defs = []
        for t in tools:
            schema = t.args_schema.model_json_schema() if t.args_schema else {"type": "object", "properties": {}}
            tool_defs.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": schema,
                },
            })
        clone._bound_tools = tool_defs
        return clone

    async def ainvoke(self, messages, **kwargs):
        """Call LiteLLM and return a LangChain-compatible response."""
        from langchain_core.messages import AIMessage, ToolCall

        lm_messages = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                lm_messages.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                lm_messages.append({"role": "user", "content": msg.content})
            else:
                lm_messages.append({"role": "assistant", "content": msg.content or ""})

        call_kwargs: dict = {
            "model": self.model,
            "messages": lm_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.api_key:
            call_kwargs["api_key"] = self.api_key
        if self.base_url:
            call_kwargs["api_base"] = self.base_url
        if self._bound_tools:
            call_kwargs["tools"] = self._bound_tools

        response = await acompletion(**call_kwargs)
        choice = response.choices[0]
        content = choice.message.content or ""

        tool_calls = []
        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                import json
                args = tc.function.arguments
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append(ToolCall(
                    name=tc.function.name,
                    args=args,
                    id=tc.id,
                ))

        return AIMessage(content=content, tool_calls=tool_calls)


async def load_agent_config(
    agent_id: uuid.UUID,
    session_factory: async_sessionmaker,
) -> Agent:
    """Load a full agent config from the database."""
    async with session_factory() as session:
        stmt = select(Agent).where(Agent.id == agent_id, Agent.is_active.is_(True))
        result = await session.execute(stmt)
        agent = result.scalar_one_or_none()
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found or inactive")

        # Eagerly load relationships by accessing them within the session
        _ = agent.model
        _ = agent.tools
        _ = agent.data_sources
        return agent


def _build_scope(data_sources: list[AgentDataSource]) -> DataSourceScope:
    """Build a DataSourceScope from the agent's data source config."""
    es_indices = []
    pg_schemas = []
    for ds in data_sources:
        if ds.source_type == "elasticsearch":
            es_indices.append(ds.source_identifier)
        elif ds.source_type == "postgresql":
            pg_schemas.append(ds.source_identifier)
    return DataSourceScope(allowed_es_indices=es_indices, allowed_pg_schemas=pg_schemas)


async def execute_agent(
    agent_id: uuid.UUID,
    user_input: str,
    triggered_by: uuid.UUID,
    session_factory: async_sessionmaker,
    es_client: AsyncElasticsearch,
    timeout: int = 120,
) -> dict:
    """Load an agent config, build the LangGraph agent, execute, and return results.

    Returns:
        dict with keys: run_id, status, output, error_message, token_usage,
        iterations, duration_ms.
    """
    # 1. Load agent config
    agent_config = await load_agent_config(agent_id, session_factory)

    # 2. Create the run record
    run = Run(
        agent_id=agent_id,
        status="running",
        input={"prompt": user_input},
        triggered_by=triggered_by,
    )
    async with session_factory() as session:
        session.add(run)
        await session.commit()
        await session.refresh(run)
        run_id = run.id

    logger.info("agent_run_start", run_id=str(run_id), agent_id=str(agent_id))

    # 3. Build tools
    scope = _build_scope(agent_config.data_sources)
    tool_names = [at.tool.name for at in agent_config.tools]
    tool_configs = {at.tool.name: at.tool_config or {} for at in agent_config.tools}

    tool_registry = get_registry()
    tools = tool_registry.build_tools(
        tool_names=tool_names,
        scope=scope,
        es_client=es_client,
        session_factory=session_factory,
        tool_configs=tool_configs,
    )

    # 4. Build LLM
    model_config = agent_config.model
    llm = _LiteLLMChatModel(
        model=f"{model_config.provider}/{model_config.model_id}",
        temperature=float(agent_config.temperature),
        max_tokens=model_config.max_tokens,
        base_url=model_config.base_url,
    )

    # 5. Build LangGraph ReAct agent
    audit_callback = AuditCallbackHandler(run_id=run_id, session_factory=session_factory)
    graph = create_react_agent(llm, tools)

    # 6. Execute
    start_time = time.monotonic()
    status = "completed"
    output = None
    error_message = None

    try:
        result = await graph.ainvoke(
            {"messages": [
                SystemMessage(content=agent_config.system_prompt),
                HumanMessage(content=user_input),
            ]},
            config={"callbacks": [audit_callback], "recursion_limit": agent_config.max_iterations * 2},
        )

        # Extract final message
        messages = result.get("messages", [])
        if messages:
            final_msg = messages[-1]
            output = {"response": final_msg.content if hasattr(final_msg, "content") else str(final_msg)}
        else:
            output = {"response": ""}

    except Exception as exc:
        status = "failed"
        error_message = str(exc)[:2000]
        logger.error("agent_run_failed", run_id=str(run_id), error=error_message, exc_info=True)

    duration_ms = int((time.monotonic() - start_time) * 1000)
    iterations = audit_callback._step_counter

    # 7. Update run record
    async with session_factory() as session:
        run_update = (await session.execute(select(Run).where(Run.id == run_id))).scalar_one()
        run_update.status = status
        run_update.output = output
        run_update.error_message = error_message
        run_update.duration_ms = duration_ms
        run_update.iterations = iterations
        run_update.completed_at = datetime.now(timezone.utc)
        await session.commit()

    logger.info(
        "agent_run_complete",
        run_id=str(run_id),
        status=status,
        duration_ms=duration_ms,
        iterations=iterations,
    )

    return {
        "run_id": str(run_id),
        "status": status,
        "output": output,
        "error_message": error_message,
        "iterations": iterations,
        "duration_ms": duration_ms,
    }
