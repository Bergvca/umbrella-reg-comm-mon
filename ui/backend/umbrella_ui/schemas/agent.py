"""Pydantic schemas for agent CRUD and execution endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# --- Data Sources ---

class DataSourceConfig(BaseModel):
    source_type: Literal["elasticsearch", "postgresql"]
    source_identifier: str


# --- Models ---

class ModelCreate(BaseModel):
    name: str
    provider: str
    model_id: str
    base_url: str | None = None
    api_key_secret: str | None = None
    max_tokens: int = 4096


class ModelUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    model_id: str | None = None
    base_url: str | None = None
    api_key_secret: str | None = None
    max_tokens: int | None = None
    is_active: bool | None = None


class ModelOut(BaseModel):
    id: uuid.UUID
    name: str
    provider: str
    model_id: str
    base_url: str | None
    max_tokens: int
    is_active: bool
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# --- Tools ---

class ToolOut(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    description: str
    category: str
    parameters_schema: dict
    is_active: bool
    created_at: datetime


# --- Agents ---

class AgentCreate(BaseModel):
    name: str
    description: str | None = None
    model_id: uuid.UUID
    system_prompt: str
    temperature: float = 0.0
    max_iterations: int = 10
    output_schema: dict | None = None
    tool_ids: list[uuid.UUID] = Field(default_factory=list)
    tool_configs: dict[str, dict] | None = None
    data_sources: list[DataSourceConfig] = Field(default_factory=list)


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    model_id: uuid.UUID | None = None
    system_prompt: str | None = None
    temperature: float | None = None
    max_iterations: int | None = None
    output_schema: dict | None = None
    is_active: bool | None = None
    tool_ids: list[uuid.UUID] | None = None
    tool_configs: dict[str, dict] | None = None
    data_sources: list[DataSourceConfig] | None = None


class ToolSummary(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    tool_config: dict | None = None


class AgentOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    model: ModelOut
    system_prompt: str
    temperature: float
    max_iterations: int
    output_schema: dict | None
    tools: list[ToolSummary]
    data_sources: list[DataSourceConfig]
    is_builtin: bool
    is_active: bool
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# --- Runs ---

class RunCreate(BaseModel):
    agent_id: uuid.UUID
    input: str


class RunStepOut(BaseModel):
    id: uuid.UUID
    step_order: int
    step_type: str
    tool_name: str | None
    input: dict
    output: dict | None
    token_usage: dict | None
    duration_ms: int | None
    created_at: datetime


class RunOut(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    status: str
    input: dict
    output: dict | None
    error_message: str | None
    token_usage: dict | None
    iterations: int | None
    duration_ms: int | None
    triggered_by: uuid.UUID
    created_at: datetime
    completed_at: datetime | None
    steps: list[RunStepOut] | None = None
