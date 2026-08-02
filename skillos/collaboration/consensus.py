"""拜占庭共识 — ByzantineConsensus（L4 协作层）

职责：
  - 多 Agent 提案、投票、达成共识，门限 = (2n)//3 + 1，容错上限 = (n-1)//3
  - 用于成果契约 L4 仲裁的多方验证（验收节点对同一证据独立判定）

语义约定：
  - APPROVE 达到门限 → 共识达成（REACHED / APPROVE）
  - REJECT 达到门限 → 共识失败（FAILED / REJECT）
  - 票满但仍未达到任何门限 → 共识失败（FAILED / None）
  - 未满票且未达门限 → 挂起（PENDING / None）
"""

import uuid
from dataclasses import dataclass, field
from enum import StrEnum

__all__ = ["ByzantineConsensus", "ConsensusResult", "ConsensusStatus", "Proposal", "VoteValue"]


class VoteValue(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class ConsensusStatus(StrEnum):
    PENDING = "pending"
    REACHED = "reached"
    FAILED = "failed"


@dataclass
class Proposal:
    proposal_id: str
    agent_id: str
    data: dict
    votes: dict = field(default_factory=dict)


@dataclass
class ConsensusResult:
    status: ConsensusStatus
    final_decision: VoteValue | None
    required_agreements: int
    total_agents: int


class ByzantineConsensus:
    def __init__(self, total_agents: int):
        if total_agents < 1:
            raise ValueError("total_agents must be >= 1")
        self.total_agents = total_agents
        self._proposals: dict[str, Proposal] = {}

    @property
    def required_agreements(self) -> int:
        """达成共识所需票数：(2n)//3 + 1。"""
        return (2 * self.total_agents) // 3 + 1

    @property
    def max_faulty(self) -> int:
        """可容忍的故障/恶意节点上限：(n-1)//3。"""
        return (self.total_agents - 1) // 3

    def propose(self, agent_id: str, data: dict) -> str:
        proposal_id = f"prop-{uuid.uuid4().hex[:12]}"
        self._proposals[proposal_id] = Proposal(
            proposal_id=proposal_id,
            agent_id=agent_id,
            data=data,
        )
        return proposal_id

    def get_proposal(self, proposal_id: str) -> Proposal | None:
        return self._proposals.get(proposal_id)

    def vote(self, proposal_id: str, agent_id: str, value: VoteValue) -> None:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError("Proposal not found")
        if agent_id in proposal.votes:
            raise ValueError("Agent already voted")
        proposal.votes[agent_id] = value

    def is_consensus_reached(self, proposal_id: str) -> bool:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            return False
        return self._count(proposal, VoteValue.APPROVE) >= self.required_agreements or self._count(
            proposal, VoteValue.REJECT
        ) >= self.required_agreements

    def finalize(self, proposal_id: str) -> ConsensusResult:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError("Proposal not found")

        approve = self._count(proposal, VoteValue.APPROVE)
        reject = self._count(proposal, VoteValue.REJECT)

        if approve >= self.required_agreements:
            return ConsensusResult(
                ConsensusStatus.REACHED, VoteValue.APPROVE, self.required_agreements, self.total_agents
            )
        if reject >= self.required_agreements:
            return ConsensusResult(
                ConsensusStatus.FAILED, VoteValue.REJECT, self.required_agreements, self.total_agents
            )
        if len(proposal.votes) >= self.total_agents:
            return ConsensusResult(ConsensusStatus.FAILED, None, self.required_agreements, self.total_agents)

        return ConsensusResult(ConsensusStatus.PENDING, None, self.required_agreements, self.total_agents)

    def reset(self) -> None:
        self._proposals.clear()

    @staticmethod
    def _count(proposal: Proposal, value: VoteValue) -> int:
        return sum(1 for v in proposal.votes.values() if v == value)
