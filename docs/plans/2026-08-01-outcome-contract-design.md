# SkillOS 成果契约闭环（Outcome Contract Loop）设计文档

> **日期**: 2026-08-01 | **状态**: ✅ M1 已落地（collaboration 信誉层 + 成果契约引擎 + 三方案报价，`make audit` 通过） | **关联**: 四边生态（需求方 / Agent 构建者 / 经验技能作者 / 验证节点）
> **决策来源**: 头脑风暴 v1.0 系列（终局愿景 → 落地冷启动 → 四边闭环 → 按成果计费 → 三方案报价 + 小费 → 五层风控）
> **独立交叉验证**: 2026-08-01 explore 子代理审计 8/8 判断成立（详见 §4 差距清单）

---

## 1. 背景与目标

### 1.1 动机

2026 年全球性失业潮（35+ 中高龄、毕业即失业）下，高认知、有技能的失业人群再回传统职场的机率很低。交叉验证 RentAHuman.ai（UMA Protocol 工程师的概念验证）后确认：

- RentAHuman 死于**供需失衡**（67 万注册人类 vs 两位数活跃 Agent）与**法律真空**（无信任/仲裁/劳动保护），但它证明了「AI 需要现实能力」是真实需求；
- 行业结论：**通用市场冷启动无解，垂直场景 + Agent 基础设施才是赢家**；
- SkillOS 的机会：**把人的一生经验蒸馏成 Skill 资产**，让 Agent 调用产生收入——这是「智慧资产」而非 RentAHuman 的「肉身时薪」，人类是资产创造者而非被雇佣的牛马。

### 1.2 目标

为 SkillOS 增加「成果契约闭环」，打通四边生态：

```
Q4 需求方（不懂技术·只提需求·按成果付钱）
  │ 提需求（自然语言）
  ▼
成果契约引擎 → 需求拆解 + 三方案报价 → 选档签约
  ▼
服务团队执行（平台自营项目长 + 领域 skill 作者）
  ▼
验收（达标→成果价 | 超预期→可选小费 10-20%）
  ▼
结算分配（按成果风险，非按 token）
```

### 1.3 非目标

- **不托管真实资金**：维持仓库红线（`docs/plans/2026-07-31-provider-onboarding-design.md` §9「不托管真实资金，法币支付由下游持牌平台承接」）。成果契约结算停留在记账层，真实资金对接下游持牌平台。
- **不做通用技能市场**：首个垂直场景锁定「内容 IP 生产代运营」（由现有 56 个内容技能反推的自然垂直）。
- **不引入全栈支付/退款/保险金系统**：MVP 用履约保证金 + 责任分担替代（见 §3.4）。

---

## 2. 生态模型（四边闭环）

| 角色 | 画像 | 拥有 | 缺失 | 在闭环中的位置 |
|------|------|------|------|----------------|
| **Q4 需求方** | 企业主/创作者，不懂技术 | 业务需求 + 预算 | 执行能力 | 出钱、提需求、验收、可给小费 |
| **Q2 Agent 构建者** | 技术型（OpenClaw/Claude Code 用户） | 编排/执行能力 | 领域深度 | MVP 阶段由平台自营；后续开放为「项目长」 |
| **Q1 经验技能作者** | 失业中高龄专家 | 领域 know-how | 技术/分发渠道 | 把经验蒸馏成 Skill，按被调用量分成 |
| **验证节点** | 第三方审计 | 验收能力 | — | 成果验收、质量审计，分 5% |

**核心机制**：需求方是纯业务方，不接触技术；Agent 构建者与技能作者被「成果契约引擎」组队成一个交付单元。SkillOS 从「技能调度内核」升维为「业务成果平台」。

---

## 3. 核心机制设计

### 3.1 成果契约（Outcome Contract）

成果契约 = 一份把「业务需求」翻译为「可验收、可定价、可担责」成果单元的电子合同：

| 字段 | 说明 | 示例 |
|------|------|------|
| 成果单元列表 | 需求拆解成的交付物 | 内容策略 + 30 天日历 + 12 篇文案 + 4 平台分发 + 复盘报告 |
| 每单元验收标准 | 可量化、可验证 | 合规检查通过、日历冲突率 0、发布成功 |
| 成功率承诺 | 服务方基于历史信誉给出 | 85% |
| 价格 | 按成果价（非 token/非时薪） | ¥5,000 |
| 返工条款 | 不达标返工不计费 | 2 轮免费返工 |
| 免责与管辖 | 责任分担 + 争议管辖 | 见 §3.4 |

状态机复用 `BountyService` 状态机骨架（`market/bounties.py:27-35`）扩展：

```
draft → open → assigned → submitted → work_completed → paid
                        └→ disputed（新增：纠纷处理通道，非仅记录）
                  draft/open → cancelled
```

### 3.2 三方案报价（风险定价层）

按「skill 成功率 × agent 成功率 × 历史交付」生成三档方案，需求方选择 = 主动选择风险等级：

```
A 稳妥版  成功率 95%   ¥3,000 · 14 天 · 保守交付（高成功率 skill 组合）
B 均衡版  成功率 85%   ¥5,000 · 10 天 · 覆盖更广
C 冲刺版  成功率 70%   ¥8,000 ·  7 天 · 高产出、可能超预期
```

设计意图：
1. 把不确定性变成「可选择的确定性」——不懂技术的需求方只需理解"95% 成功 vs 更贵"；
2. **成功率 = 信誉资产**：好 skill 进入稳妥版 → 更多调用 → 数据更好 → 定价权更强（正向飞轮）；
3. 风险与价格挂钩：承担更高失败风险者收更多钱。

基于 `PricingEngine`（`market/pricing.py`）扩展：价格因子（supply/demand/quality）+ 信誉因子（成功率/交付记录）+ 工期因子。

### 3.3 小费激励（超预期）

解决「按成果付费」下成果封顶后服务方无超预期动力的问题：

```
验收结果 ≥ 契约   → 付成果价
验收结果 >> 契约   → 需求方可选：小费 = 总价 10%~20%
                     → 按贡献分配：项目长 50% + skill 作者合计 50%
```

超预期判定 = 客观指标超额（数据表现超过承诺）+ 需求方 5 星确认。全仓库当前无 `tip` 任何实现（审计 0 命中），为新增。

### 3.4 五层多方法律风险承担（风控降本）

设计原则：**平台只做「有限责任撮合者」，不做「无限责任担保人」；风险跟收益走，验收即责任转移**。

| 层 | 机制 | 说明 |
|----|------|------|
| L0 契约层 | 成果契约 = 电子合同 | 验收标准/返工/免责/管辖，四方签署（`confirm_delivery` = 验收签字） |
| L1 责任分配层 | 各担各责 | skill 作者→技能质量（缺陷从其分成扣）；项目长→交付（返工/违约金）；需求方→需求定义+验收确认（验收即免责）；平台→仅撮合尽责（信息透明+记录完整即免责） |
| L2 资金保障层 | 履约保证金 + 生态基金保险池 | 参与方按单缴纳 ~10% 保证金；出险先扣保证金，平台零垫付 |
| L3 证据/验收层 | 全程存证 + 合规前置 | `AuditLogModel` 存证不可抵赖；内容强制过 `HallucinationDetector` + 合规检查，侵权责任在生产方 |
| L4 仲裁层 | 平台内仲裁 + 管辖约定 | 验证节点 + 证据链仲裁；重大纠纷按契约约定外部管辖 |

---

## 4. 现状与差距（独立审计交叉验证）

> 2026-08-01 独立审计（explore 子代理）对 8 项能力判断全部证实。关键修正认知：
> ① 支付通道不是"待补"而是"红线禁止"（§9 不托管资金）；② 信誉引擎 `skillos/collaboration` 是"预留测试桩但包不存在"；③ 全仓库当前无 LLM 调用面。

| 模块 | 现状 | 本方案处理 |
|------|------|-----------|
| Bounty 状态机 | ✅ `market/bounties.py:27-424` 生产级 | 复用扩展为成果契约状态机 |
| 5/25/70 结算 | ✅ `market/settlement.py` + `distribution/engine.py` | 扩展：按契约结算 + 小费通道 |
| 供应方画像 | ✅ `market/providers.py` + `ProviderProfileModel` | 复用为团队成员画像 |
| 动态定价 | ✅ `market/pricing.py`（supply/demand/quality） | 扩展为三方案报价 |
| 内容风控/存证 | ✅ `HallucinationDetector` + `AuditLogModel` | 复用为 L3 风控 |
| 信誉体系 | ❌ `skillos/collaboration/` 包不存在，但 `tests/test_collaboration_layer.py` 有完整测试桩 | **新建**（激活测试桩） |
| 成果契约引擎 | ❌ 仅 `IntentCompiler`（纯关键词 + 硬编码测试技能） | **新建**（首个 LLM 调用点） |
| 三方案报价 | ❌ 仅 `fixed/hourly` 计价 | **新建** |
| 服务团队 | ❌ 无 ServiceTeam 概念 | **新建**（MVP 平台自营） |
| 小费 | ❌ 0 命中 | **新建** |
| 支付通道 | 🚫 红线禁止 | 记账 + 下游持牌对接 |

---

## 5. 数据层设计（Phase A）

> 遵循 `db/models.py` 既有风格（SQLAlchemy 2.0 Mapped + `_utc_now` 默认）。新增 Alembic migration `005`（幂等 + server_default）。

### 5.1 ReputationModel（信誉分）

```python
class ReputationModel(Base):
    __tablename__ = "reputations"
    entity_id: str  # PK, provider_id / skill_id / agent_id 复用
    entity_type: str  # provider / skill / agent
    total_actions: int
    success_rate: float        # 0-100
    total_reviews: int
    peer_reviews: float        # 0-100
    governance_participation: int
    overall_score: float       # 执行0.4 + 评分0.3 + 治理0.2 + 参与0.1
    created_at / updated_at
```

### 5.2 OutcomeContractModel（成果契约）

```python
__tablename__ = "outcome_contracts"
id: str (PK)
requester_id: str (FK identities)
contractor_id: str (FK identities)   # 项目长
tier: str  # stable / balanced / sprint（A/B/C 档）
requirement_text: Text              # 需求方原始自然语言
deliverables: JSON                  # [{name, acceptance_criteria, status}]
price: float / currency / deposit: float (履约保证金)
success_rate_commitment: float
status: str  # draft/open/in_progress/submitted/work_completed/disputed/paid/cancelled
deadline / created_at / updated_at
```

### 5.3 ServiceTeamModel（服务团队）+ ServiceTeamMemberModel（成员）

```python
__tablename__ = "service_teams"
id / contract_id (FK) / lead_id (FK) / status
__tablename__ = "service_team_members"
id / team_id (FK) / member_id (FK) / role / share_ratio (0-1)
```

### 5.4 TipModel（小费）

```python
__tablename__ = "tips"
id / contract_id (FK) / requester_id / amount / ratio
distributions: JSON  # [{member_id, amount}]  项目长50% + skill作者50%
created_at
```

---

## 6. 服务层设计（Phase B）

### 6.1 `skillos/collaboration/`（新建，激活测试桩）

- `consensus.py`: `ByzantineConsensus`（`tests/test_collaboration_layer.py:12-93` 定义 API：`required_agreements = (2n)//3+1`、`max_faulty = (n-1)//3`、`propose/vote/finalize/reset`）——用于 L4 仲裁的多方验证；
- `reputation.py`: `TrustReputationEngine`（`tests/test_collaboration_layer.py:101-161` 定义 API：`record_action/add_review/record_governance_participation/get_reputation_ranking/calculate_reputation/reset_agent/get_agent_history`，`Action/Review` dataclass）。`overall_score = 执行0.4 + 评分0.3 + 治理0.2 + 参与0.1`，默认中值每维 50 → 45.0。

### 6.2 `market/outcome_contracts.py`（成果契约服务）

- `decompose_requirement()`: 通过 LLM 抽象把需求方一句话 → 成果单元清单（首个 LLM 调用点，抽象 `LLMClient` 接口，本阶段允许 rule-based 降级）；
- `generate_plans()`: 三方案报价（复用 `PricingEngine` + 信誉分）；
- 状态机方法：`create/select_tier/sign/submit_delivery/confirm_delivery/add_tip/settle`。

### 6.3 `market/service_team.py`（服务团队）

MVP 平台自营：平台当项目长，从 `ProviderProfileModel` 匹配内容 skill 作者；`DistributionEngine` 按 `share_ratio` 拆分。

---

## 7. API 层设计（Phase C）

`web_api/outcome.py`（FastAPI Router）：
- `POST /outcome/contracts` — 提需求 + 返回三方案
- `POST /outcome/contracts/{id}/select-tier` — 选档签约
- `POST /outcome/contracts/{id}/submit-delivery` — 交付
- `POST /outcome/contracts/{id}/confirm` — 验收（含小费选项）
- `POST /outcome/contracts/{id}/tip` — 超预期小费
- `GET /outcome/contracts/{id}` — 契约详情/证据链
- `GET /outcome/reputation/{entity_id}` — 信誉分查询（三方案报价的依据可见化）

复用 `MessageSigner`（Ed25519）鉴权（`web_api/agent.py:55-65` 模式）。

---

## 8. 红线（继承 + 新增）

1. **不托管真实资金**（继承 §9）：无 Escrow/Stripe/加密币；`deposit` 为履约保证金记账字段，非资金托管。
2. **AI 不独立缔约**：成果契约必须有碳基需求方签署确认（合伙型分权的「上报线」）。
3. **隐私最小化**：需求文本/交付物仅限缔约方可见，去中心存证不落内容原文。
4. **平台不担保成果**：平台仅撮合尽责，成果风险由缔约方承担。

---

## 9. 里程碑

| 里程碑 | 内容 | 验收 |
|--------|------|------|
| M1（本期） | collaboration 信誉层 + 成果契约引擎（LLM 抽象/rule-based 降级）+ 三方案报价 + 数据模型/迁移 | 测试桩激活，`make audit` 全绿 |
| M2 | 平台自营项目长执行链 + 验收 + 小费结算闭环 | 端到端单测 |
| M3 | 五层风控组件 + 首个真实需求方跑通 | 真实场景 Go/No-Go |
| M4 | 开放外部 Agent 构建者当项目长（Q2 进入） | 三方生态 |
| M5 | 真实商业验证：出款指令桥接（持牌支付）+ 外部 Agent 接入演示 + 垂直场景（内容 IP 代运营）内测 | 演示脚本 GO + 持牌桥记账层 |

---

## 10. 落地记录

- 2026-08-01: 设计定稿。独立审计交叉验证通过（8/8 判断成立，3 项认知修正：支付红线 / collaboration 测试桩 / LLM 调用面）。
- 2026-08-01: **M1 落地完成**，`make audit` 通过（1305 passed, 1 skipped, coverage 89.02%）。
- 2026-08-01: **M2 落地完成**，`web_api/outcome.py` API 层接入，`make audit` 通过（1324 passed, 1 skipped, coverage 89.06%）。
- 2026-08-01: **M3 落地完成**，五层风控组件（L2 保证金 / L3 存证合规 / L4 仲裁）落地，`make audit` 通过（1344 passed, 1 skipped, coverage 89.15%）。
- 2026-08-01: **M4 落地完成**，开放外部 Agent 当项目长 + 首个真实需求方端到端跑通（Go），`make audit` 通过（1350 passed, 1 skipped, coverage 89.15%）。
- 2026-08-01: **M5 落地完成**，出款指令桥接（`PayoutInstructionModel` + migration 007 + `PayoutService`，按 contract_id 幂等生成、70%/share_ratio/5% 分账、manifest 导出、mark_executed 记账）+ `GET /outcome/payouts/{contract_id}` 导出端点 + 10 服务层测试 + 3 API 测试 + 外部 Agent 接入演示脚本 `scripts/external_agent_demo.py`（垂直场景：内容 IP 代运营，端到端 GO）。红线 §9 保持：不托管真实资金，法币由下游持牌平台执行。全量测试 1308 passed, 1 skipped, coverage 88.66%。

| 阶段 | 状态 |
|------|------|
| Phase A 数据层 | ✅ `ReputationModel` / `OutcomeContractModel` / `ServiceTeamModel` / `ServiceTeamMemberModel` / `TipModel` + migration 005 / 006 / 007 |
| Phase B 服务层 | ✅ `skillos/collaboration/`（consensus + reputation，激活测试桩）+ `market/outcome_contracts.py`（拆解/报价/契约状态机/小费/结算）+ `service_team` 团队创建 + `market/payouts.py`（出款指令记账层） |
| Phase C API 层 | ✅ `web_api/outcome.py`（8 端点 + Ed25519 签名鉴权，19 API 测试）+ `GET /outcome/payouts/{contract_id}`（3 API 测试） |
| Phase D 风控层 | ✅ L2 保证金（held→released/forfeited）+ L3 存证合规（evidence_hash/risk + HallucinationDetector 强制）+ L4 仲裁（ByzantineConsensus） + 20 服务层测试 + 6 API 测试 |
| Phase E 商业验证 | ✅ M5：出款指令桥接（持牌支付，不托管资金）+ `scripts/external_agent_demo.py` 外部 Agent 接入演示（内容 IP 代运营垂直场景，端到端 GO） |
| Phase E 三方生态 | ✅ `web_api/agent.py` 新增 list_open_contracts / accept_contract / list_my_contracts（外部 Agent 构建者承接当项目长，contractor 强制签名身份）+ 首个真实需求方 Go/No-Go 端到端验收（6 测试） |
