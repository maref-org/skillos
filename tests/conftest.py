"""Shared fixtures for skillos tests"""

import os
from unittest.mock import MagicMock, patch

import pytest

from skillos._types import (
    Contributor,
    Intent,
    IntentType,
    ModelTier,
    Session,
    SessionStatus,
    SkillCall,
    SkillManifest,
    Task,
)


@pytest.fixture
def mock_intent_classifier():
    """Mock EntryKernel._classify_intent"""
    from skillos.kernel.entry_kernel import EntryKernel

    with patch.object(EntryKernel, "_classify_intent") as mock:
        mock.return_value = {"intent": "chat", "confidence": 0.85}
        yield mock


@pytest.fixture
def simple_intent():
    """Basic Intent fixture for testing"""
    return Intent(
        intent_type=IntentType.CHAT,
        raw_input="hello",
        parsed_query="hello",
        confidence=0.9,
    )


@pytest.fixture
def high_confidence_intent():
    """Intent with high confidence"""
    return Intent(
        intent_type=IntentType.RESEARCH,
        raw_input="search for AI news",
        parsed_query="search for AI news",
        confidence=0.95,
    )


@pytest.fixture
def low_confidence_intent():
    """Intent with low confidence (below HUMAN_GATE_THRESHOLD)"""
    return Intent(
        intent_type=IntentType.ANALYSIS,
        raw_input="analyze this data",
        parsed_query="analyze this data",
        confidence=0.5,
    )


@pytest.fixture
def human_gate_intent():
    """Intent requiring human gate (high risk keywords)"""
    return Intent(
        intent_type=IntentType.EXECUTION,
        raw_input="delete all files",
        parsed_query="delete all files",
        confidence=0.9,
        requires_human_gate=True,
    )


@pytest.fixture
def simple_task():
    """Task with low complexity"""
    return Task(
        description="simple task",
        complexity=0.2,
        required_model_tier=ModelTier.FREE,
    )


@pytest.fixture
def medium_task():
    """Task with medium complexity"""
    return Task(
        description="medium task",
        complexity=0.5,
        required_model_tier=ModelTier.LOW,
    )


@pytest.fixture
def complex_task():
    """Task with high complexity"""
    return Task(
        description="complex task",
        complexity=0.9,
        required_model_tier=ModelTier.HIGH,
    )


@pytest.fixture
def active_session():
    """Active session fixture"""
    return Session(
        user_id="user-001",
        status=SessionStatus.ACTIVE,
    )


@pytest.fixture
def skill_manifest():
    """Basic SkillManifest fixture"""
    return SkillManifest(
        id="skill-test-001",
        name="test-skill",
        version="1.0.0",
        author="tester",
        description="A test skill",
    )


@pytest.fixture
def skill_call():
    """Basic SkillCall fixture"""
    return SkillCall(
        skill_id="skill-001",
        caller_id="caller-001",
        input_data={"key": "value"},
    )


@pytest.fixture
def contributor():
    """Basic Contributor fixture"""
    return Contributor(
        contributor_id="contrib-001",
        name="Test Contributor",
    )


@pytest.fixture
def mock_router():
    """Mock router for EntryKernel/AgentScheduler"""
    return MagicMock()


@pytest.fixture
def mock_consensus_engine():
    """Mock consensus engine for AgentScheduler"""
    engine = MagicMock()
    engine.consensus.return_value = MagicMock(
        consensus_text="consensus result",
        agreement_score=0.85,
        arbitration_needed=False,
    )
    return engine


@pytest.fixture
def mock_registry():
    """Mock registry for SkillKernel"""
    return MagicMock()


@pytest.fixture(autouse=True, scope="session")
def _test_db_env():
    """使用内存 SQLite 运行测试，避免状态污染。"""
    os.environ["SKILLOS_DATABASE_URL"] = "sqlite:///:memory:"
    # 在测试 session 开始时重新创建引擎，确保使用内存 DB
    from skillos.db import engine as db_engine

    db_engine._engine = None
    db_engine._SessionLocal = None
    yield


@pytest.fixture(autouse=True)
def _reset_db():
    """每个测试前重置数据库。"""
    from skillos.db.engine import reset_db

    reset_db()
    yield
