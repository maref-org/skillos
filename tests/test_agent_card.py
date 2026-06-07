"""Tests for skillos.protocol.agent_card — AgentCard Registry"""

import tempfile
from pathlib import Path

import pytest

from skillos.protocol.agent_card import AgentCard, AgentRegistry


@pytest.fixture
def registry():
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "test_registry.db")
        reg = AgentRegistry(db_path=db)
        yield reg


@pytest.fixture
def sample_card():
    return AgentCard(
        agent_id="agent-001",
        name="Research Agent",
        version="1.0.0",
        capabilities=["research", "analysis"],
        skills=["skill-web", "skill-data"],
        endpoint="http://localhost:9001",
        public_key="pubkey-001",
    )


@pytest.fixture
def second_card():
    return AgentCard(
        agent_id="agent-002",
        name="Coding Agent",
        version="2.0.0",
        capabilities=["coding", "review"],
        skills=["skill-python"],
        endpoint="http://localhost:9002",
    )


class TestAgentCard:
    def test_from_dict(self):
        data = {
            "agent_id": "test-1",
            "name": "Test",
            "version": "1.0",
            "capabilities": '["a", "b"]',
            "skills": '["s1"]',
            "metadata": '{"key": "val"}',
            "endpoint": "http://localhost",
            "public_key": "",
            "status": "active",
            "registered_at": 1000.0,
            "last_heartbeat": 1000.0,
        }
        card = AgentCard.from_dict(data)
        assert card.agent_id == "test-1"
        assert card.capabilities == ["a", "b"]
        assert card.skills == ["s1"]
        assert card.metadata == {"key": "val"}

    def test_default_fields(self):
        card = AgentCard(agent_id="new-agent", name="New")
        assert card.version == "1.0.0"
        assert card.status == "active"
        assert card.capabilities == []
        assert card.registered_at > 0


class TestAgentRegistry:
    def test_register_and_get(self, registry, sample_card):
        registry.register(sample_card)
        retrieved = registry.get_agent("agent-001")
        assert retrieved is not None
        assert retrieved.name == "Research Agent"
        assert retrieved.capabilities == ["research", "analysis"]

    def test_get_nonexistent(self, registry):
        assert registry.get_agent("nonexistent") is None

    def test_register_overwrites(self, registry, sample_card):
        registry.register(sample_card)
        updated = AgentCard(
            agent_id="agent-001",
            name="Updated Agent",
            capabilities=["new-cap"],
            skills=[],
        )
        registry.register(updated)
        retrieved = registry.get_agent("agent-001")
        assert retrieved.name == "Updated Agent"
        assert retrieved.capabilities == ["new-cap"]

    def test_discover_all(self, registry, sample_card, second_card):
        registry.register(sample_card)
        registry.register(second_card)
        agents = registry.discover()
        assert len(agents) == 2

    def test_discover_by_capability(self, registry, sample_card, second_card):
        registry.register(sample_card)
        registry.register(second_card)
        research_agents = registry.discover(capability="research")
        assert len(research_agents) == 1
        assert research_agents[0].agent_id == "agent-001"

    def test_discover_by_skill(self, registry, sample_card, second_card):
        registry.register(sample_card)
        registry.register(second_card)
        python_agents = registry.discover(skill="skill-python")
        assert len(python_agents) == 1
        assert python_agents[0].agent_id == "agent-002"

    def test_discover_by_status(self, registry, sample_card, second_card):
        registry.register(sample_card)
        registry.register(second_card)
        registry.update_status("agent-002", "suspended")
        active = registry.discover(status="active")
        assert len(active) == 1
        assert active[0].agent_id == "agent-001"

    def test_heartbeat(self, registry, sample_card):
        registry.register(sample_card)
        assert registry.heartbeat("agent-001") is True
        card = registry.get_agent("agent-001")
        assert card.last_heartbeat > 0

    def test_heartbeat_nonexistent(self, registry):
        assert registry.heartbeat("ghost") is False

    def test_update_status(self, registry, sample_card):
        registry.register(sample_card)
        assert registry.update_status("agent-001", "suspended") is True
        card = registry.get_agent("agent-001")
        assert card.status == "suspended"
        assert registry.update_status("nonexistent", "active") is False

    def test_prune_inactive(self, registry, sample_card, second_card):
        registry.register(sample_card)
        registry.register(second_card)
        pruned = registry.prune_inactive(timeout_seconds=0)
        assert pruned >= 0

    def test_unregister(self, registry, sample_card):
        registry.register(sample_card)
        assert registry.get_agent("agent-001") is not None
        assert registry.unregister("agent-001") is True
        assert registry.get_agent("agent-001") is None
        assert registry.unregister("agent-001") is False

    def test_count(self, registry, sample_card, second_card):
        assert registry.count() == 0
        registry.register(sample_card)
        assert registry.count() == 1
        registry.register(second_card)
        assert registry.count() == 2
        registry.update_status("agent-002", "inactive")
        assert registry.count(status="active") == 1
        assert registry.count(status="inactive") == 1

    def test_get_stats(self, registry, sample_card, second_card):
        registry.register(sample_card)
        registry.register(second_card)
        registry.update_status("agent-002", "inactive")
        stats = registry.get_stats()
        assert stats["total"] == 2
        assert stats["active"] == 1
        assert stats["inactive"] == 1

    def test_cache_hit(self, registry, sample_card):
        registry.register(sample_card)
        card1 = registry.get_agent("agent-001")
        card2 = registry.get_agent("agent-001")
        assert card1 is card2
