"""Collaboration Layer (L4) — 多 Agent 协作与信任治理。

子模块：
  - consensus: ByzantineConsensus 拜占庭共识（提案/投票/共识达成）
  - reputation: TrustReputationEngine 声誉评分引擎（执行/评价/治理三维加权）
"""

from skillos.collaboration.consensus import (
    ByzantineConsensus,
    ConsensusResult,
    ConsensusStatus,
    Proposal,
    VoteValue,
)
from skillos.collaboration.reputation import (
    Action,
    ReputationScore,
    Review,
    TrustReputationEngine,
)

__all__ = [
    "Action",
    "ByzantineConsensus",
    "ConsensusResult",
    "ConsensusStatus",
    "Proposal",
    "ReputationScore",
    "Review",
    "TrustReputationEngine",
    "VoteValue",
]
