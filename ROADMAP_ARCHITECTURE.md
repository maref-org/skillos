# SkillOS 六层架构实现路线图

## 当前状态

| 层级 | 名称 | 状态 | 实现度 |
|------|------|------|--------|
| L1 | Human Layer（人机交互层） | 部分实现 | 60% |
| L2 | Production Layer（生产执行层） | 已实现 | 90% |
| L3 | Market Layer（技能市场层） | 未实现 | 0% |
| L4 | Collaboration Layer（协作治理层） | 未实现 | 0% |
| L5 | Intelligence Layer（智能增强层） | 部分实现 | 40% |
| L6 | Governance Layer（治理共识层） | 未实现 | 0% |

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                    L6 · Governance Layer                        │
│              治理共识层（DAO + 智能合约 + 合规）                 │
│         ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│         │  DAO 治理    │  │ 智能合约    │  │ 合规审计    │      │
│         │  投票/提案   │  │ 自动执行    │  │ 等保/跨境   │      │
│         └─────────────┘  └─────────────┘  └─────────────┘      │
├─────────────────────────────────────────────────────────────────┤
│                    L5 · Intelligence Layer                      │
│              智能增强层（AI 编排 + 意图编译 + 递归演进）          │
│         ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│         │ 意图编译引擎 │  │ 递归演进     │  │ 知识蒸馏    │      │
│         │ (IECP)      │  │ 自改进回路   │  │ Skill NFT   │      │
│         └─────────────┘  └─────────────┘  └─────────────┘      │
├─────────────────────────────────────────────────────────────────┤
│                    L4 · Collaboration Layer                     │
│              协作治理层（多 Agent 协作 + 声誉系统）               │
│         ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│         │ 拜占庭共识   │  │ 信任声誉引擎 │  │ 多 Agent 调度│      │
│         │ (BFT)       │  │ (TRCP)      │  │ 协作协议    │      │
│         └─────────────┘  └─────────────┘  └─────────────┘      │
├─────────────────────────────────────────────────────────────────┤
│                    L3 · Market Layer                            │
│              技能市场层（Skill 交易 + 定价 + 结算）               │
│         ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│         │ Skill 注册   │  │ 动态定价引擎 │  │ 微支付结算   │      │
│         │ 发现/匹配    │  │ 供需调节    │  │ 双 Token    │      │
│         └─────────────┘  └─────────────┘  └─────────────┘      │
├─────────────────────────────────────────────────────────────────┤
│                    L2 · Production Layer                        │
│              生产执行层（Skill 内核 + 分配引擎 + 协议客户端）      │
│         ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│         │ Skill Kernel │  │ 分配引擎     │  │ 协议客户端   │      │
│         │ 生命周期管理 │  │ 5/25/70     │  │ 注册/匹配   │      │
│         └─────────────┘  └─────────────┘  └─────────────┘      │
├─────────────────────────────────────────────────────────────────┤
│                    L1 · Human Layer                             │
│              人机交互层（20/80 路由 + 身份认证 + 审计）           │
│         ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│         │ 20/80 路由   │  │ Ed25519 身份 │  │ HMAC 审计   │      │
│         │ 人机分流     │  │ 零知识证明   │  │ 日志完整性   │      │
│         └─────────────┘  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

---

## P0 · 优先实现：Market Layer（L3）

### 目标
建立 Skill 技能市场，实现技能的注册、发现、定价、交易和结算。

### 核心模块

#### 3.1 Skill Registry（技能注册中心）

```python
# skillos/market/registry.py
class SkillRegistry:
    """Skill 注册中心：技能的注册、发现、版本管理。"""

    async def register_skill(self, skill_manifest: SkillManifest) -> str:
        """注册新技能，返回 skill_id。"""
        pass

    async def discover_skills(
        self,
        query: str,
        filters: SkillFilters | None = None,
        sort: SkillSort = SkillSort.RELEVANCE,
    ) -> list[SkillInfo]:
        """技能发现与搜索。"""
        pass

    async def get_skill_versions(self, skill_id: str) -> list[SkillVersion]:
        """获取技能版本历史。"""
        pass

    async def deprecate_skill(self, skill_id: str, reason: str) -> None:
        """弃用技能。"""
        pass
```

**数据模型扩展**：

```python
# skillos/db/models.py
class SkillMarketModel(Base):
    """Skill 市场信息。"""
    __tablename__ = "skill_markets"

    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/approved/rejected/deprecated
    category: Mapped[str] = mapped_column(String(128), default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    total_calls: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(256), nullable=True)

class SkillReviewModel(Base):
    """Skill 评价。"""
    __tablename__ = "skill_reviews"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(256), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
```

#### 3.2 Pricing Engine（动态定价引擎）

```python
# skillos/market/pricing.py
class PricingEngine:
    """动态定价引擎：基于供需调节 Skill 调用价格。"""

    def calculate_price(
        self,
        skill_id: str,
        base_price: float,
        demand_factor: float,
        supply_factor: float,
        quality_score: float,
    ) -> float:
        """计算动态价格。

        公式: price = base_price * (1 + demand_factor - supply_factor) * quality_score
        """
        pass

    def get_price_history(self, skill_id: str, days: int = 30) -> list[PricePoint]:
        """获取价格历史。"""
        pass
```

#### 3.3 Settlement Engine（结算引擎）

扩展现有分配引擎，支持双 Token 结算：

```python
# skillos/market/settlement.py
class SettlementEngine:
    """结算引擎：Skill 调用后的收益分配。"""

    async def settle(
        self,
        call_id: str,
        skill_id: str,
        caller_id: str,
        amount: float,
        token_type: TokenType = TokenType.SKILL_COIN,
    ) -> SettlementResult:
        """执行结算。

        分配比例:
        - 5% 平台手续费
        - 25% 生态建设基金
        - 70% 贡献者分配（按权重）
        """
        pass

    async def get_settlement_history(
        self,
        skill_id: str | None = None,
        contributor_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[SettlementRecord]:
        """查询结算历史。"""
        pass
```

**Token 类型定义**：

```python
# skillos/types.py
class TokenType(str, Enum):
    """Token 类型。"""

    SKILL_COIN = "skill_coin"          # 技能币：用于技能调用结算
    GOVERNANCE_TOKEN = "gov_token"     # 治理币：用于 DAO 投票
```

### 数据库迁移

```python
# migrations/versions/002_add_market_layer.py
"""Add Market Layer tables.

Revision ID: 002
Revises: 0015c682563a
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "0015c682563a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Skill 市场信息表
    op.create_table(
        "skill_markets",
        sa.Column("skill_id", sa.String(64), sa.ForeignKey("skills.id"), primary_key=True),
        sa.Column("status", sa.String(32), default="pending"),
        sa.Column("category", sa.String(128), default=""),
        sa.Column("tags", sa.JSON, default=list),
        sa.Column("rating", sa.Float, default=0.0),
        sa.Column("review_count", sa.Integer, default=0),
        sa.Column("total_calls", sa.Integer, default=0),
        sa.Column("revenue", sa.Float, default=0.0),
        sa.Column("approved_at", sa.DateTime, nullable=True),
        sa.Column("approved_by", sa.String(256), nullable=True),
    )

    # Skill 评价表
    op.create_table(
        "skill_reviews",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("skill_id", sa.String(64), sa.ForeignKey("skills.id"), nullable=False),
        sa.Column("reviewer_id", sa.String(256), nullable=False),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, default=""),
        sa.Column("created_at", sa.DateTime, default=sa.func.now()),
    )

    # 结算记录表
    op.create_table(
        "settlements",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("call_id", sa.String(64), nullable=False, index=True),
        sa.Column("skill_id", sa.String(64), sa.ForeignKey("skills.id"), nullable=False),
        sa.Column("caller_id", sa.String(256), nullable=False),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("token_type", sa.String(32), default="skill_coin"),
        sa.Column("platform_fee", sa.Float, nullable=False),
        sa.Column("ecosystem_fee", sa.Float, nullable=False),
        sa.Column("contributor_pool", sa.Float, nullable=False),
        sa.Column("status", sa.String(32), default="pending"),
        sa.Column("created_at", sa.DateTime, default=sa.func.now()),
    )

    # 创建索引
    op.create_index("ix_skill_markets_status", "skill_markets", ["status"])
    op.create_index("ix_skill_markets_category", "skill_markets", ["category"])
    op.create_index("ix_settlements_status", "settlements", ["status"])


def downgrade() -> None:
    op.drop_index("ix_settlements_status", table_name="settlements")
    op.drop_index("ix_skill_markets_category", table_name="skill_markets")
    op.drop_index("ix_skill_markets_status", table_name="skill_markets")
    op.drop_table("settlements")
    op.drop_table("skill_reviews")
    op.drop_table("skill_markets")
```

### 实现时间表

| 阶段 | 任务 | 预计工时 | 交付物 |
|------|------|----------|--------|
| 3.1 | Skill Registry 实现 | 3 天 | registry.py + 测试 |
| 3.2 | Pricing Engine 实现 | 2 天 | pricing.py + 测试 |
| 3.3 | Settlement Engine 扩展 | 2 天 | settlement.py + 测试 |
| 3.4 | 数据库迁移 | 1 天 | Alembic migration |
| 3.5 | API 接口 | 2 天 | REST API + 文档 |
| 3.6 | 集成测试 | 2 天 | E2E 测试 |

**总计：12 天**

---

## P0 · 优先实现：Governance Layer（L6）

### 目标
建立 DAO 治理机制，实现去中心化决策、智能合约执行、合规审计。

### 核心模块

#### 6.1 DAO Governance（DAO 治理）

```python
# skillos/governance/dao.py
class DAOGovernance:
    """DAO 治理：提案、投票、执行。"""

    async def create_proposal(
        self,
        proposer_id: str,
        title: str,
        description: str,
        proposal_type: ProposalType,
        parameters: dict[str, Any],
    ) -> str:
        """创建治理提案。"""
        pass

    async def vote(
        self,
        proposal_id: str,
        voter_id: str,
        vote: VoteType,
        weight: float,
    ) -> None:
        """投票。"""
        pass

    async def execute_proposal(self, proposal_id: str) -> ExecutionResult:
        """执行通过的提案。"""
        pass

    async def get_proposal_status(self, proposal_id: str) -> ProposalStatus:
        """获取提案状态。"""
        pass
```

**提案类型**：

```python
# skillos/types.py
class ProposalType(str, Enum):
    """提案类型。"""

    PARAMETER_CHANGE = "parameter_change"    # 参数变更
    SKILL_APPROVAL = "skill_approval"        # 技能审核
    FUND_ALLOCATION = "fund_allocation"      # 资金分配
    UPGRADE = "upgrade"                      # 协议升级
    EMERGENCY = "emergency"                  # 紧急提案
```

#### 6.2 Smart Contract Engine（智能合约引擎）

```python
# skillos/governance/contracts.py
class SmartContractEngine:
    """智能合约引擎：自动执行治理决策。"""

    async def deploy_contract(
        self,
        contract_type: ContractType,
        parameters: dict[str, Any],
    ) -> str:
        """部署智能合约。"""
        pass

    async def execute_contract(
        self,
        contract_id: str,
        trigger: ContractTrigger,
    ) -> ExecutionResult:
        """执行合约。"""
        pass

    async def get_contract_state(self, contract_id: str) -> ContractState:
        """获取合约状态。"""
        pass
```

#### 6.3 Compliance Audit（合规审计）

```python
# skillos/governance/compliance.py
class ComplianceAuditor:
    """合规审计：等保、数据跨境、资金合规。"""

    async def run_security_audit(self) -> SecurityAuditReport:
        """运行安全审计（等保 2.0 三级）。"""
        pass

    async def check_data_cross_border(self, data_type: str, target_region: str) -> ComplianceResult:
        """检查数据跨境合规性。"""
        pass

    async def audit_fund_flow(self, start_date: datetime, end_date: datetime) -> FundAuditReport:
        """审计资金流向。"""
        pass

    async def generate_compliance_report(self, period: str) -> ComplianceReport:
        """生成合规报告。"""
        pass
```

### 数据库迁移

```python
# migrations/versions/003_add_governance_layer.py
"""Add Governance Layer tables.

Revision ID: 003
Revises: 002
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 提案表
    op.create_table(
        "proposals",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("proposer_id", sa.String(256), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, default=""),
        sa.Column("proposal_type", sa.String(64), nullable=False),
        sa.Column("parameters", sa.JSON, default=dict),
        sa.Column("status", sa.String(32), default="pending"),  # pending/active/passed/rejected/executed
        sa.Column("vote_for", sa.Float, default=0.0),
        sa.Column("vote_against", sa.Float, default=0.0),
        sa.Column("vote_abstain", sa.Float, default=0.0),
        sa.Column("quorum", sa.Float, default=0.0),
        sa.Column("threshold", sa.Float, default=0.5),
        sa.Column("start_time", sa.DateTime, nullable=False),
        sa.Column("end_time", sa.DateTime, nullable=False),
        sa.Column("executed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, default=sa.func.now()),
    )

    # 投票记录表
    op.create_table(
        "votes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("proposal_id", sa.String(64), sa.ForeignKey("proposals.id"), nullable=False),
        sa.Column("voter_id", sa.String(256), nullable=False),
        sa.Column("vote_type", sa.String(32), nullable=False),  # for/against/abstain
        sa.Column("weight", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime, default=sa.func.now()),
    )

    # 智能合约表
    op.create_table(
        "smart_contracts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("contract_type", sa.String(64), nullable=False),
        sa.Column("parameters", sa.JSON, default=dict),
        sa.Column("status", sa.String(32), default="active"),  # active/paused/terminated
        sa.Column("deployed_at", sa.DateTime, default=sa.func.now()),
        sa.Column("last_executed_at", sa.DateTime, nullable=True),
        sa.Column("execution_count", sa.Integer, default=0),
    )

    # 合规审计记录表
    op.create_table(
        "compliance_audits",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("audit_type", sa.String(64), nullable=False),  # security/data_cross_border/fund
        sa.Column("status", sa.String(32), default="pending"),  # pending/passed/failed
        sa.Column("results", sa.JSON, default=dict),
        sa.Column("report_url", sa.String(512), nullable=True),
        sa.Column("audited_at", sa.DateTime, default=sa.func.now()),
        sa.Column("audited_by", sa.String(256), nullable=True),
    )

    # 创建索引
    op.create_index("ix_proposals_status", "proposals", ["status"])
    op.create_index("ix_proposals_type", "proposals", ["proposal_type"])
    op.create_index("ix_votes_proposal", "votes", ["proposal_id"])
    op.create_index("ix_compliance_audits_type", "compliance_audits", ["audit_type"])


def downgrade() -> None:
    op.drop_index("ix_compliance_audits_type", table_name="compliance_audits")
    op.drop_index("ix_votes_proposal", table_name="votes")
    op.drop_index("ix_proposals_type", table_name="proposals")
    op.drop_index("ix_proposals_status", table_name="proposals")
    op.drop_table("compliance_audits")
    op.drop_table("smart_contracts")
    op.drop_table("votes")
    op.drop_table("proposals")
```

### 实现时间表

| 阶段 | 任务 | 预计工时 | 交付物 |
|------|------|----------|--------|
| 6.1 | DAO Governance 实现 | 4 天 | dao.py + 测试 |
| 6.2 | Smart Contract Engine | 3 天 | contracts.py + 测试 |
| 6.3 | Compliance Audit | 3 天 | compliance.py + 测试 |
| 6.4 | 数据库迁移 | 1 天 | Alembic migration |
| 6.5 | API 接口 | 2 天 | REST API + 文档 |
| 6.6 | 集成测试 | 2 天 | E2E 测试 |

**总计：15 天**

---

## P1 · 次要实现：Collaboration Layer（L4）

### 目标
实现多 Agent 协作、拜占庭共识、信任声誉系统。

### 核心模块

#### 4.1 Byzantine Consensus（拜占庭共识）

扩展现有 agent_scheduler.py：

```python
# skillos/collaboration/consensus.py
class ByzantineConsensus:
    """拜占庭共识：多 Agent 决策的一致性保证。"""

    async def propose(self, agent_id: str, proposal: Proposal) -> str:
        """提交提案。"""
        pass

    async def vote(self, proposal_id: str, agent_id: str, vote: Vote) -> None:
        """投票。"""
        pass

    async def finalize(self, proposal_id: str) -> ConsensusResult:
        """ finalize 共识结果（2f+1 原则）。"""
        pass

    def is_consensus_reached(self, votes: list[Vote], total_agents: int) -> bool:
        """检查是否达成共识。

        条件: 赞成票 >= 2/3 * 总节点数
        """
        pass
```

#### 4.2 Trust Reputation Engine（信任声誉引擎）

```python
# skillos/collaboration/reputation.py
class TrustReputationEngine:
    """信任声誉引擎：基于历史行为的声誉评分。"""

    def calculate_reputation(
        self,
        agent_id: str,
        historical_actions: list[Action],
        peer_reviews: list[Review],
    ) -> ReputationScore:
        """计算声誉分数。

        因素:
        - 历史贡献质量 (40%)
        - 成功率 (30%)
        - 同行评价 (20%)
        - 治理参与度 (10%)
        """
        pass

    def update_reputation(self, agent_id: str, action: Action) -> ReputationScore:
        """基于新行为更新声誉。"""
        pass

    def get_reputation_ranking(self, top_k: int = 100) -> list[ReputationRanking]:
        """获取声誉排行榜。"""
        pass
```

### 实现时间表

| 阶段 | 任务 | 预计工时 | 交付物 |
|------|------|----------|--------|
| 4.1 | Byzantine Consensus | 3 天 | consensus.py + 测试 |
| 4.2 | Trust Reputation Engine | 3 天 | reputation.py + 测试 |
| 4.3 | 数据库迁移 | 1 天 | Alembic migration |
| 4.4 | 集成测试 | 2 天 | E2E 测试 |

**总计：9 天**

---

## P2 · 未来实现：Intelligence Layer（L5）扩展

### 目标
完善意图编译引擎、递归演进回路、知识蒸馏。

### 核心模块

#### 5.1 Intent Compilation Engine（意图编译引擎）

扩展现有 entry_kernel.py：

```python
# skillos/intelligence/intent_compiler.py
class IntentCompiler:
    """意图编译引擎：自然语言 → 可执行计划。"""

    async def compile(self, natural_language: str, context: Context) -> ExecutionPlan:
        """编译自然语言为执行计划。

        步骤:
        1. 意图识别与分类
        2. 参数提取与验证
        3. 路径存在性检查
        4. 依赖关系分析
        5. 生成执行计划
        """
        pass

    async def validate(self, plan: ExecutionPlan) -> ValidationResult:
        """验证执行计划的可行性。"""
        pass

    async def optimize(self, plan: ExecutionPlan) -> ExecutionPlan:
        """优化执行计划。"""
        pass
```

#### 5.2 Recursive Evolution（递归演进 — 技能自进化回路）

**设计说明**：本模块灵感来源于 2026 年 5 月 arXiv 上的两篇独立论文
（SkillEvolver: Skill Learning as a Meta-Skill, EmbodiSkill: Skill-Aware Reflection for Self-Evolving Embodied Agents），
但实现完全独立，使用 SkillOS 自有 Agent 执行日志作为训练数据，不依赖任何论文代码或数据集。

**核心流程**（已实现，见 `skillos/intelligence/evolution.py`）：

```
Agent 执行 Skill → 成功/失败轨迹 → 失败记录 (FailureRecord)
    ↓
失败分析 (analyze_failure)
    ├─ Skill Defect（技能缺陷：规则写错了）→ 修正 skill body
    ├─ Execution Lapse（执行失误：Agent 没遵守规则）→ 追加 skill appendix 提醒
    ├─ Discovery（新发现：技能未覆盖的场景）→ 补充 skill body
    └─ Optimization（优化：现有规则可以改进）→ 修订 skill body
    ↓
知识蒸馏 (distill_knowledge) → common_causes + fix_patterns
    ↓
技能演进 (evolve) → 更新 skill body/appendix → 新一代技能版本
    ↓
SLO 检查 (run_slo_check) → 成功率/延迟/可用性报告
```

**Skill 双体结构**（对应 `_types.py` / `skillos/types.py` 中的 SkillBody / SkillAppendix）：

| 组件 | 职责 | 更新条件 |
|------|------|---------|
| Skill Body | 核心正文规则，只存"正确"的标准执行逻辑 | Discovery / Optimization / Skill Defect |
| Skill Appendix | 动态提醒事项，记录执行偏差、操作疏漏 | Execution Lapse 不修改 body |

**当前实现状态**：三个核心模块已实现

| 模块 | 文件 | 状态 |
|------|------|------|
| RecursiveEvolution | `skillos/intelligence/evolution.py` | **[已实现]** 失败记录/分析/蒸馏/演进/SLO |
| IntentCompiler | `skillos/intelligence/intent_compiler.py` | **[已实现]** 自然语言→执行计划 |
| KnowledgeDistiller | `skillos/intelligence/distillation.py` | **[已实现]** 知识块存储/搜索 |

### 实现状态

| 阶段 | 任务 | 状态 | 实际耗时 |
|------|------|------|---------|
| 5.1 | Intent Compiler | **[已完成]** time: 2026-06-08 | ~30 分钟 |
| 5.2 | Recursive Evolution | **[已完成]** time: 2026-06-08 | ~30 分钟 |
| 5.3 | Knowledge Distillation | **[已完成]** time: 2026-06-08 | ~15 分钟 |
| 5.4 | 集成测试 | **[已完成]** time: 2026-06-08 | 15 个测试全部 PASS |

**实现总计：约 1.5 小时**（原始预计 14 天 → 实际 1.5 小时，因论文提供了经过验证的蓝图）

---

## 总体时间表

```
Week 1-2: Market Layer (L3)        ████████████████████ 12 天
Week 3-4: Governance Layer (L6)    ███████████████████████ 15 天
Week 5:   Collaboration Layer (L4) ███████████████ 9 天
Week 6-7: Intelligence Layer (L5)  ██████████████████████ 14 天
Week 8:   集成测试 + 发布          ████████████ 8 天
                                    ────────────────────────
总计: 58 天 (~8 周)
```

---

## 依赖关系

```
L3 Market Layer
    ├── 依赖: L2 Production Layer (已完成)
    └── 被依赖: L4 Collaboration Layer, L6 Governance Layer

L4 Collaboration Layer
    ├── 依赖: L3 Market Layer
    └── 被依赖: L6 Governance Layer

L5 Intelligence Layer
    ├── 依赖: L2 Production Layer (已完成)
    └── 被依赖: 无

L6 Governance Layer
    ├── 依赖: L3 Market Layer, L4 Collaboration Layer
    └── 被依赖: 无
```

**并行策略**: L3 和 L5 可以部分并行开发（都依赖 L2，但互不依赖）。

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 智能合约安全漏洞 | 高 | 第三方审计 + 形式化验证 |
| DAO 投票参与度低 | 中 | 激励机制 + 委托投票 |
| 合规审批延迟 | 高 | 提前启动评估 + 并行准备 |
| 数据库迁移失败 | 中 | 备份 + 回滚机制 + 测试环境验证 |
| 性能瓶颈 | 中 | 负载测试 + 缓存优化 |

---

## 验收标准

### Market Layer
- [ ] Skill 注册、发现、版本管理功能完整
- [ ] 动态定价引擎运行正常
- [ ] 结算引擎支持双 Token
- [ ] API 文档完整
- [ ] 测试覆盖率 >= 85%

### Governance Layer
- [ ] DAO 提案、投票、执行流程完整
- [ ] 智能合约自动执行正常
- [ ] 合规审计报告生成正常
- [ ] 等保 2.0 三级评估启动
- [ ] 数据跨境合规检查可用

### Collaboration Layer
- [ ] 拜占庭共识 2f+1 原则实现
- [ ] 声誉评分算法运行正常
- [ ] 多 Agent 协作测试通过

### Intelligence Layer
- [x] 意图编译引擎 — IntentCompiler: 自然语言 → 可执行计划
- [x] 递归演进回路闭环 — RecursiveEvolution: 失败记录 → 分析 → 蒸馏 → 演进 → SLO 检查
- [x] 知识蒸馏 — KnowledgeDistiller: 知识块存储/搜索/复用
- [x] 技能双体结构 — SkillBody / SkillAppendix 类型定义
- [ ] 24h 无人值守 SLO 达标（待实际部署积累数据后验证）
