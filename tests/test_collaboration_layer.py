"""Tests for skillos.collaboration — Collaboration Layer (L4)

覆盖:
  - ByzantineConsensus: 提案、投票、共识
  - TrustReputationEngine: 声誉评分、排行榜
"""

import pytest

pytest.importorskip("skillos.collaboration")

from skillos.collaboration.consensus import (
    ByzantineConsensus,
    ConsensusStatus,
    VoteValue,
)
from skillos.collaboration.reputation import (
    Action,
    Review,
    TrustReputationEngine,
)


# ---------------------------------------------------------------------------
# ByzantineConsensus tests
# ---------------------------------------------------------------------------

class TestByzantineConsensus:
    @pytest.fixture
    def consensus(self):
        return ByzantineConsensus(total_agents=5)

    def test_required_agreements(self, consensus):
        assert consensus.required_agreements == 4  # (2*5)//3 + 1 = 4

    def test_max_faulty(self, consensus):
        assert consensus.max_faulty == 1  # (5-1)//3 = 1

    def test_propose(self, consensus):
        proposal_id = consensus.propose("agent-001", {"action": "test"})
        assert proposal_id
        proposal = consensus.get_proposal(proposal_id)
        assert proposal is not None
        assert proposal.agent_id == "agent-001"

    def test_vote_and_reach_consensus(self, consensus):
        proposal_id = consensus.propose("agent-001", {"action": "test"})
        consensus.vote(proposal_id, "agent-001", VoteValue.APPROVE)
        consensus.vote(proposal_id, "agent-002", VoteValue.APPROVE)
        consensus.vote(proposal_id, "agent-003", VoteValue.APPROVE)
        consensus.vote(proposal_id, "agent-004", VoteValue.APPROVE)

        assert consensus.is_consensus_reached(proposal_id)
        result = consensus.finalize(proposal_id)
        assert result.status == ConsensusStatus.REACHED
        assert result.final_decision == VoteValue.APPROVE

    def test_vote_and_fail_consensus(self, consensus):
        proposal_id = consensus.propose("agent-001", {"action": "test"})
        consensus.vote(proposal_id, "agent-001", VoteValue.REJECT)
        consensus.vote(proposal_id, "agent-002", VoteValue.REJECT)
        consensus.vote(proposal_id, "agent-003", VoteValue.REJECT)
        consensus.vote(proposal_id, "agent-004", VoteValue.REJECT)
        consensus.vote(proposal_id, "agent-005", VoteValue.APPROVE)

        result = consensus.finalize(proposal_id)
        assert result.status == ConsensusStatus.FAILED
        assert result.final_decision == VoteValue.REJECT

    def test_duplicate_vote(self, consensus):
        proposal_id = consensus.propose("agent-001", {"action": "test"})
        consensus.vote(proposal_id, "agent-001", VoteValue.APPROVE)
        with pytest.raises(ValueError, match="Agent already voted"):
            consensus.vote(proposal_id, "agent-001", VoteValue.APPROVE)

    def test_vote_nonexistent_proposal(self, consensus):
        with pytest.raises(ValueError, match="Proposal not found"):
            consensus.vote("nonexistent", "agent-001", VoteValue.APPROVE)

    def test_pending_consensus(self, consensus):
        proposal_id = consensus.propose("agent-001", {"action": "test"})
        consensus.vote(proposal_id, "agent-001", VoteValue.APPROVE)
        consensus.vote(proposal_id, "agent-002", VoteValue.APPROVE)

        assert not consensus.is_consensus_reached(proposal_id)
        result = consensus.finalize(proposal_id)
        assert result.status == ConsensusStatus.PENDING

    def test_reset(self, consensus):
        proposal_id = consensus.propose("agent-001", {"action": "test"})
        consensus.vote(proposal_id, "agent-001", VoteValue.APPROVE)
        consensus.reset()
        assert consensus.get_proposal(proposal_id) is None


# ---------------------------------------------------------------------------
# TrustReputationEngine tests
# ---------------------------------------------------------------------------

class TestTrustReputationEngine:
    @pytest.fixture
    def engine(self):
        return TrustReputationEngine()

    def test_record_action(self, engine):
        action = Action(action_type="skill_call", success=True, timestamp=0.0)
        engine.record_action("agent-001", action)
        score = engine.get_reputation("agent-001")
        assert score is not None
        assert score.total_actions == 1
        assert score.success_rate == 100.0

    def test_add_review(self, engine):
        review = Review(reviewer_id="user-001", rating=5.0, comment="great", timestamp=0.0)
        engine.add_review("agent-001", review)
        score = engine.get_reputation("agent-001")
        assert score is not None
        assert score.total_reviews == 1
        assert score.peer_reviews == 100.0

    def test_record_governance_participation(self, engine):
        engine.record_governance_participation("agent-001")
        score = engine.get_reputation("agent-001")
        assert score is not None
        assert score.governance_participation > 0

    def test_reputation_ranking(self, engine):
        # Agent 1: 高质量
        for _ in range(10):
            engine.record_action("agent-001", Action(action_type="skill_call", success=True, timestamp=0.0))
        engine.add_review("agent-001", Review(reviewer_id="user-001", rating=5.0, comment="", timestamp=0.0))

        # Agent 2: 低质量
        for _ in range(10):
            engine.record_action("agent-002", Action(action_type="skill_call", success=False, timestamp=0.0))
        engine.add_review("agent-002", Review(reviewer_id="user-001", rating=1.0, comment="", timestamp=0.0))

        ranking = engine.get_reputation_ranking(top_k=2)
        assert len(ranking) == 2
        assert ranking[0].agent_id == "agent-001"
        assert ranking[0].overall_score > ranking[1].overall_score

    def test_default_score(self, engine):
        score = engine.get_reputation("agent-001")
        assert score is None
        score = engine.calculate_reputation("agent-001")
        # 默认中值：所有维度为 50，但治理参与度为 0（无参与）
        # 50*0.4 + 50*0.3 + 50*0.2 + 0*0.1 = 45.0
        assert score.overall_score == 45.0

    def test_reset_agent(self, engine):
        engine.record_action("agent-001", Action(action_type="skill_call", success=True, timestamp=0.0))
        engine.reset_agent("agent-001")
        assert engine.get_reputation("agent-001") is None

    def test_agent_history(self, engine):
        engine.record_action("agent-001", Action(action_type="skill_call", success=True, timestamp=0.0))
        history = engine.get_agent_history("agent-001")
        assert len(history["actions"]) == 1
        assert history["governance_count"] == 0
