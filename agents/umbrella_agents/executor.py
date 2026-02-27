"""Agent execution engine — builds and runs LangGraph ReAct agents."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime

import litellm
import structlog
from elasticsearch import AsyncElasticsearch
from langchain_litellm import ChatLiteLLM
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from umbrella_agents.callbacks.audit import AuditCallbackHandler
from umbrella_agents.callbacks.streaming import StreamingAuditCallback
from umbrella_agents.db.models import Agent, AgentDataSource, Model, Run
from umbrella_agents.tool_call_parser import TextToolCallingWrapper
from umbrella_agents.tools.registry import DataSourceScope, get_registry

logger = structlog.get_logger()

# Models already registered with litellm (avoid repeated calls).
_registered_models: set[str] = set()

# Preamble prepended to every agent's system prompt so the LLM understands
# that tools are real, live, and must be invoked via function calling — not
# simulated or output as text.
_TOOL_PREAMBLE = """\
You have access to real, live tools that are connected to production systems. \
When you use a tool, it will be executed automatically and the real results \
will be returned to you. Do NOT simulate, fabricate, or imagine tool results. \
Do NOT output tool calls as text — use the function calling mechanism provided. \
You are NOT in a simulation. Every tool call you make will run against real \
databases and return real data. Always call tools when you need data instead \
of guessing.

"""


def _ensure_model_registered(model_config: Model) -> str:
    """Register a model with litellm so it knows the model supports tool calling.

    LiteLLM maintains an internal registry of known models and their
    capabilities.  Custom or self-hosted deployments (e.g. DeepSeek on Azure)
    are unknown to litellm, which causes ``supports_function_calling()`` to
    return False and silently strips the ``tools`` parameter from API
    requests.  This function registers the model once so tool calling works.
    """
    model_str = f"{model_config.provider}/{model_config.model_id}"
    if model_str in _registered_models:
        return model_str

    if not litellm.supports_function_calling(model=model_str):
        litellm.register_model({
            model_str: {
                "max_tokens": model_config.max_tokens,
                "input_cost_per_token": 0.0,
                "output_cost_per_token": 0.0,
                "litellm_provider": model_config.provider,
                "mode": "chat",
                "supports_function_calling": True,
            }
        })
        logger.info(
            "registered_model_for_tool_calling",
            model=model_str,
        )

    _registered_models.add(model_str)
    return model_str


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

    # 4. Build LLM (wrapped to handle text-based tool calls)
    model_config = agent_config.model
    model_str = _ensure_model_registered(model_config)
    llm_kwargs: dict[str, Any] = {
        "model": model_str,
        "temperature": float(agent_config.temperature),
        "max_tokens": model_config.max_tokens,
        "api_base": model_config.base_url,
    }
    if isinstance(model_config.api_key_secret, str) and model_config.api_key_secret:
        llm_kwargs["api_key"] = model_config.api_key_secret
    base_llm = ChatLiteLLM(**llm_kwargs)
    llm = TextToolCallingWrapper(delegate=base_llm)

    # 5. Build LangGraph ReAct agent
    audit_callback = AuditCallbackHandler(run_id=run_id, session_factory=session_factory)
    graph = create_react_agent(llm, tools)

    # 6. Execute
    start_time = time.monotonic()
    status = "completed"
    output = None
    error_message = None

    try:
        system_prompt = _TOOL_PREAMBLE + agent_config.system_prompt
        result = await graph.ainvoke(
            {"messages": [
                SystemMessage(content=system_prompt),
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
        run_update.completed_at = datetime.now(UTC).replace(tzinfo=None)
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


async def execute_agent_streaming(
    agent_id: uuid.UUID,
    user_input: str,
    triggered_by: uuid.UUID,
    run_id: uuid.UUID,
    session_factory: async_sessionmaker,
    es_client: AsyncElasticsearch,
    event_queue: asyncio.Queue,
    cancelled: asyncio.Event,
    timeout: int = 120,
) -> None:
    """Execute an agent with streaming events pushed to *event_queue*.

    Designed to run as a background ``asyncio.Task``.  Pushes a terminal
    event (``run_completed`` / ``run_failed`` / ``run_cancelled``) and
    finally a ``None`` sentinel to signal end-of-stream.
    """

    async def _push(event: str, data: dict) -> None:
        try:
            event_queue.put_nowait({"event": event, "data": data})
        except asyncio.QueueFull:
            logger.warning("event_queue_full", run_id=str(run_id), event=event)

    try:
        # 1. Load agent config
        agent_config = await load_agent_config(agent_id, session_factory)

        # 2. Create run record
        run = Run(
            id=run_id,
            agent_id=agent_id,
            status="running",
            input={"prompt": user_input},
            triggered_by=triggered_by,
        )
        async with session_factory() as session:
            session.add(run)
            await session.commit()

        await _push("run_started", {
            "run_id": str(run_id),
            "agent_id": str(agent_id),
            "status": "running",
        })

        logger.info("agent_stream_run_start", run_id=str(run_id), agent_id=str(agent_id))

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

        # 4. Build LLM (wrapped to handle text-based tool calls)
        model_config = agent_config.model
        model_str = _ensure_model_registered(model_config)
        llm_kwargs: dict[str, Any] = {
            "model": model_str,
            "temperature": float(agent_config.temperature),
            "max_tokens": model_config.max_tokens,
            "api_base": model_config.base_url,
        }
        if isinstance(model_config.api_key_secret, str) and model_config.api_key_secret:
            llm_kwargs["api_key"] = model_config.api_key_secret
        base_llm = ChatLiteLLM(**llm_kwargs)
        llm = TextToolCallingWrapper(delegate=base_llm)

        # 5. Build LangGraph ReAct agent with streaming callback
        streaming_callback = StreamingAuditCallback(
            run_id=run_id,
            session_factory=session_factory,
            event_queue=event_queue,
        )
        graph = create_react_agent(llm, tools)

        # 6. Execute
        start_time = time.monotonic()
        status = "completed"
        output = None
        error_message = None

        try:
            if cancelled.is_set():
                status = "cancelled"
            else:
                system_prompt = _TOOL_PREAMBLE + agent_config.system_prompt
                result = await graph.ainvoke(
                    {"messages": [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=user_input),
                    ]},
                    config={
                        "callbacks": [streaming_callback],
                        "recursion_limit": agent_config.max_iterations * 2,
                    },
                )

                if cancelled.is_set():
                    status = "cancelled"
                else:
                    messages = result.get("messages", [])
                    if messages:
                        final_msg = messages[-1]
                        output = {"response": final_msg.content if hasattr(final_msg, "content") else str(final_msg)}
                    else:
                        output = {"response": ""}

        except asyncio.CancelledError:
            status = "cancelled"
        except Exception as exc:
            status = "failed"
            error_message = str(exc)[:2000]
            logger.error("agent_stream_run_failed", run_id=str(run_id), error=error_message, exc_info=True)

        duration_ms = int((time.monotonic() - start_time) * 1000)
        iterations = streaming_callback._step_counter

        # 7. Update run record
        async with session_factory() as session:
            run_update = (await session.execute(select(Run).where(Run.id == run_id))).scalar_one()
            run_update.status = status
            run_update.output = output
            run_update.error_message = error_message
            run_update.duration_ms = duration_ms
            run_update.iterations = iterations
            run_update.completed_at = datetime.now(UTC).replace(tzinfo=None)
            await session.commit()

        logger.info(
            "agent_stream_run_complete",
            run_id=str(run_id),
            status=status,
            duration_ms=duration_ms,
            iterations=iterations,
        )

        # 8. Push terminal event
        terminal_data = {
            "run_id": str(run_id),
            "status": status,
            "iterations": iterations,
            "duration_ms": duration_ms,
        }
        if status == "completed":
            terminal_data["output"] = output
            await _push("run_completed", terminal_data)
        elif status == "failed":
            terminal_data["error_message"] = error_message
            await _push("run_failed", terminal_data)
        else:
            await _push("run_cancelled", terminal_data)

    except Exception as exc:
        # Catch-all for errors before run record is created
        logger.error("agent_stream_fatal", run_id=str(run_id), error=str(exc), exc_info=True)
        await _push("run_failed", {
            "run_id": str(run_id),
            "status": "failed",
            "error_message": str(exc)[:2000],
            "iterations": 0,
            "duration_ms": 0,
        })
    finally:
        # Sentinel to signal end of stream
        await event_queue.put(None)
