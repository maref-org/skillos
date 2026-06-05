#!/usr/bin/env python3
"""skillos.types — 共享类型定义"""

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class IntentType(StrEnum):
    SKILL_CALL = "skill_call"
    RESEARCH = "research"
    CONTENT_CREATION = "content_creation"
    ANALYSIS = "analysis"
    EXECUTION = "execution"
    CHAT = "chat"


class ExecutionPath(StrEnum):
    HUMAN_GUI = "human_gui"
    AGENT_AUTO = "agent_auto"
    HYBRID = "hybrid"


class ApprovalStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


class SkillStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    SUSPENDED = "suspended"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"


class ModelTier(StrEnum):
    FREE = "free"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Intent:
    intent_type: IntentType
    raw_input: str
    parsed_query: str
    confidence: float
    requires_human_gate: bool = False
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class Approval:
    status: ApprovalStatus
    human_decision: str | None = None
    reasoning: str | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class SkillManifest:
    id: str
    name: str
    version: str
    author: str
    description: str
    license_type: str = "AGPL-3.0"
    status: SkillStatus = SkillStatus.DRAFT
    entry_point: str | None = None
    dependencies: list[str] = field(default_factory=list)
    price_per_call: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class SkillCall:
    skill_id: str
    caller_id: str
    input_data: dict[str, Any]
    output_data: dict[str, Any] | None = None
    revenue_usd: float = 0.0
    status: str = "pending"
    call_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    latency_ms: float = 0.0


@dataclass
class Task:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    complexity: float = 0.5
    required_model_tier: ModelTier = ModelTier.LOW
    deadline: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    status: SessionStatus = SessionStatus.ACTIVE
    items: list[dict[str, Any]] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Contributor:
    contributor_id: str
    name: str
    historical_contribution: float = 0.0
    current_period_attribution: float = 0.0
    success_rate: float = 1.0
    governance_participation: float = 0.0
