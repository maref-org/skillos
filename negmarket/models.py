#!/usr/bin/env python3
"""NegMarket — data models for negative sample market"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class NegativeSample:
    id: str = field(default_factory=_new_id)
    contributor_id: str = ""
    original_hash: str = ""
    encrypted_blob: str = ""
    desensitized_pattern: dict[str, Any] = field(default_factory=dict)
    category: str = ""
    risk_level: str = "medium"
    verification_status: str = "pending"
    price_per_call: float = 0.1
    created_at: str = field(default_factory=_utc_now)


@dataclass
class AntiPatternSkill:
    id: str = field(default_factory=_new_id)
    sample_id: str = ""
    skill_manifest: dict[str, Any] = field(default_factory=dict)
    generated_by: str = ""
    call_count: int = 0
    revenue: float = 0.0
    created_at: str = field(default_factory=_utc_now)


@dataclass
class AntiPatternResult:
    risk_level: str = ""
    warning: str = ""
    anti_pattern_id: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class ZKProof:
    sample_id: str = ""
    proof_value: str = ""
    verified: bool = False
    timestamp: str = field(default_factory=_utc_now)


@dataclass
class DesensitizationContext:
    raw_text: str = ""
    contributor_id: str = ""
    desensitized_text: str = ""
    category: str = ""
    risk_level: str = "medium"
    extra: dict[str, Any] = field(default_factory=dict)
