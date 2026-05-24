"""Shared fixtures for skillos tests"""

import os
import sys

# Ensure project root is on sys.path before any imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch

import pytest

from skillos.kernel.entry_kernel import EntryKernel
from skillos.types import (
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


@pytest.fixture(scope="session", autouse=True)
def init_test_database():
    """初始化测试数据库（session 级别，只执行一次）"""
    import os
    os.environ["SKILLOS_DATABASE_URL"] = "sqlite:///:memory:"
    from skillos.db.engine import reset_db
    reset_db()
    yield
    del os.environ["SKILLOS_DATABASE_URL"]


@pytest.fixture(autouse=True)
def reset_tables():
    """每个测试前重置所有表数据"""
    from skillos.db.engine import reset_db
    reset_db()
    yield


@pytest.fixture
def db_session():
    """提供数据库会话，测试结束后自动回滚"""
    from sqlalchemy.orm import sessionmaker
    from skillos.db.engine import get_engine
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def mock_intent_classifier():
    """Mock skillos.kernel.entry_kernel._classify_intent"""
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
