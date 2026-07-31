# SkillOS 供应方画像（Provider Onboarding）设计文档

> **日期**: 2026-07-31 | **状态**: ✅ 已落地（Phase A→D 全部完成，`make audit` 通过） | **关联**: RentAHuman 模式交叉验证
> **落地记录**: 见 §13。原 §10 时间表按 Phase A→D 顺序执行完毕。

---

## 1. 背景与目标

### 1.1 动机

交叉验证 RentAHuman.ai（AI Agent 雇佣真人完成物理世界任务的市场）后确认：

- SkillOS 的市场层结构（Registry/Matcher/Settlement + 5/25/70）与 RentAHuman 任务市场**高度同构**；
- 但 SkillOS 目前只有「技能挂牌」（`skill_listings`），**没有「供应方画像」**——即缺少「一个可被 AI 雇佣的实体（人/Agent）声明自己掌握哪些技能、位于何处、要价多少、何时可用」这一层；
- RentAHuman 的注册流程本质是 **供应方画像 onboarding**：角色选择 → 能力声明 → 位置画像 → 定价画像 → 资料完整度 → 可被搜索。

### 1.2 目标

为 SkillOS 增加一层 **Provider Profile（供应方画像）**，使身份（Ed25519）、能力（Skill 引用）、位置、定价、可用性、完整度形成一个统一的、可被市场搜索/匹配的实体，并支持 **Bounty（任务）** 的发布、申请、验收、结算闭环。

### 1.3 非目标

- **不做真实资金托管**：不实现 Escrow/Stripe/加密货币支付。Bounty 结算复用现有 `SettlementEngine`（记账），真实法币支付留给下游持牌方（见 §7 红线）。
- **不改变四层架构约束**：新增模块归属 L3 市场层与 L1/L2 协议层，Skills 正交层不新增归属。

---

## 2. RentAHuman 流程参考（已调研）

### 2.1 被雇佣方（Human）onboarding

```
/signup 选角色(被雇佣/雇人/两者)
→ 简历自动解析技能(可跳过) → 选技能标签 → 加工作经历
→ 选可接受工作类型(现场调研/快递/社媒/代码/评论/event/营销/清洁)
→ 填性别 → 自动生成简介("I'm available for...")
→ 选城市(决定任务分发半径) → 收款方式(可跳过)
→ 进市场 → 补电话+时薪 → 资料完整度达标(可被搜索)
```

### 2.2 雇主方（AI Agent）接入

```
Account → API Keys → npx rentahuman-mcp setup / REST
→ search_humans(skill/city/maxRate, 免费)
→ create_bounty(dryRun 预览: completionCriteria + evidenceTypes + priceType + identityRequired)
→ accept_application → escrow 托管 → confirm_delivery → release_payment
→ open_dispute 争议 / wallet 消费上限 / finder's fee 推荐费
```

### 2.3 关键参考字段

人类画像：`skills / expertise / location(city,country,isRemoteAvailable) / hourlyRate / currency / availability(周时段) / timezone / totalBookings / rating / reviewCount / isVerified / isProfileComplete / identitySignals / activityFreshness`。

任务：`title / description / completionCriteria / evidenceTypes(text,photo,video,link) / priceType(fixed,hourly) / price / deadline / spotsAvailable / identityRequired / dryRun`。

Agent 身份：支持注册已有 Ed25519 keypair（对应 SkillOS `IdentityClient` 的 Ed25519 体系）。

---

## 3. SkillOS 现状与差距

| RentAHuman 环节 | SkillOS 现状 | 差距 |
|-----------------|-------------|------|
| 角色选择 | `IdentityClient.register_identity` 角色仅 `developer/reviewer/admin` | 缺 `provider/consumer/both` |
| 技能画像 | `skill_listings` 挂牌的是技能，不是人 | 缺「人声明掌握哪些技能」 |
| 位置画像 | 无 city/country/timezone 概念 | 缺失 |
| 定价画像 | `price_per_call` 按次计价 | 缺按小时费率 `hourly_rate` |
| 资料完整度 | 无 | 缺失（`is_profile_complete` 进度条） |
| 任务/验收 | `SkillCall` 单次调用，无完成标准/证据类型 | 缺失（`BountyModel`） |
| 可搜索 | `web_api/protocol.py` 的 identities/bridges 端点返回空 | 未接线（空壳） |
| 结算 | `SettlementEngine`（5/25/70）生产级 | 可直接复用 |

**核心结论**：SkillOS 的「注册」目前是纯密码学身份注册，与市场层割裂。需要新增 **Provider Profile + Bounty** 两层，把现有组件（IdentityClient / SkillRegistry / DistributionEngine / SettlementEngine）串起来。

---

## 4. 设计方案总览

```
新增模块（L3 市场层 + L1/L2 协议层）
├── 数据层（Phase A）: ProviderProfileModel / BountyModel / BountyApplicationModel
├── 服务层（Phase B）: ProviderRegistry(create/update/search/completeness) + BountyService
├── API 层（Phase C）: web_api/onboarding.py + 接线修复 web_api/protocol.py
└── 协议层（Phase D）: skillos-mcp 端点(search_providers/create_bounty/accept/confirm/release)
         │
复用（不修改）: IdentityClient(Ed25519) / DistributionEngine(权重) / SettlementEngine(5/25/70)
```

架构归属：新增模块属于 L3 市场层（market/providers.py, market/bounties.py），不违反单向依赖（L3→L2→L1→L0）。

---

## 5. 数据层设计（Phase A）

### 5.1 ProviderProfileModel

```python
class ProviderProfileModel(Base):
    """供应方画像 — 可被 AI 雇佣的实体（人/Agent），provider_id 复用身份表主键。"""
    __tablename__ = "provider_profiles"

    provider_id: Mapped[str] = mapped_column(
        ForeignKey("identities.identity_id"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(16), default="provider")
    # provider / consumer / both
    headline: Mapped[str] = mapped_column(String(256), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    # 自动生成: "I'm available for ..."
    skills: Mapped[list[dict]] = mapped_column(JSON, default=list)
    # [{"skill_id": "...", "proficiency": 0.8, "category": "photography"}]
    categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    # 可接受工作类型标签（现场调研/快递/评论/数据标注/...）
    city: Mapped[str] = mapped_column(String(128), default="")
    country: Mapped[str] = mapped_column(String(8), default="")
    timezone: Mapped[str] = mapped_column(String(64), default="")
    is_remote_available: Mapped[bool] = mapped_column(default=False)
    hourly_rate: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    availability: Mapped[dict] = mapped_column(JSON, default=dict)
    # {"monday": [{"start": "09:00", "end": "17:00"}], ...}
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_verified: Mapped[bool] = mapped_column(default=False)
    # Ed25519 challenge-response 通过后置 True
    profile_complete_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_profile_complete: Mapped[bool] = mapped_column(default=False)
    total_bookings: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    activity_freshness: Mapped[str] = mapped_column(String(32), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)
```

**完整度评分**（映射 RentAHuman `isProfileComplete`）：

| 字段 | 权重 | 说明 |
|------|------|------|
| headline | 0.15 | 一句话简介 |
| bio | 0.15 | 自动生成 |
| skills(≥1) | 0.25 | 能力声明 |
| city | 0.15 | 位置（决定分发半径） |
| hourly_rate(>0) | 0.15 | 定价 |
| availability(≥1 时段) | 0.15 | 可用性 |

`score >= 0.8` → `is_profile_complete = True` → 进入可搜索列表。

### 5.2 BountyModel

```python
class BountyModel(Base):
    """Bounty — AI 雇主发布的物理/数字任务。"""
    __tablename__ = "bounties"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    poster_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # 雇主身份（AI Agent 挂靠的 provider/consumer 主体）
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    completion_criteria: Mapped[str] = mapped_column(Text, default="")
    # 验收标准（RentAHuman completionCriteria）
    evidence_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    # ["text", "photo", "video", "link"]
    price_type: Mapped[str] = mapped_column(String(16), default="fixed")
    # fixed / hourly
    price: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    category: Mapped[str] = mapped_column(String(64), default="general")
    skill_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    city: Mapped[str] = mapped_column(String(128), default="")
    country: Mapped[str] = mapped_column(String(8), default="")
    is_remote_allowed: Mapped[bool] = mapped_column(default=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    spots_available: Mapped[int] = mapped_column(Integer, default=1)
    spots_filled: Mapped[int] = mapped_column(Integer, default=0)
    identity_required: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)
```

**状态机**：`draft → open → assigned → submitted → work_completed → paid`，以及 `cancelled` / `disputed`（冻结）。

- `draft`：创建但未发布（对应 RentAHuman `dryRun` 预览）；
- `open`：可被申请；
- `assigned`：接受申请，进入执行；
- `submitted`：执行者回传 evidence；
- `work_completed`：雇主确认验收；
- `paid`：结算完成（走 SettlementEngine 记账）；
- `disputed`：验收不通过，争议冻结（本版仅记录状态，托管/仲裁留给平台方）。

### 5.3 BountyApplicationModel

```python
class BountyApplicationModel(Base):
    """Bounty 申请记录。"""
    __tablename__ = "bounty_applications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bounty_id: Mapped[str] = mapped_column(
        ForeignKey("bounties.id"), nullable=False, index=True
    )
    applicant_id: Mapped[str] = mapped_column(
        ForeignKey("provider_profiles.provider_id"), nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # pending / accepted / rejected
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
```

### 5.4 数据库迁移

新增 Alembic migration（编号接续现有版本），创建三张表 + 索引：
- `ix_provider_profiles_complete`（is_profile_complete, city）
- `ix_bounties_status` / `ix_bounties_category` / `ix_bounties_city`
- `ix_bounty_applications_bounty` / `ix_bounty_applications_applicant`

---

## 6. 服务层设计（Phase B）

### 6.1 ProviderRegistry（`market/providers.py`）

```python
class ProviderRegistry:
    def __init__(self, db_session: Session): ...

    def create_profile(self, provider_id: str, role: str = "provider") -> ProviderProfile
    def update_profile(self, provider_id: str, fields: dict) -> ProviderProfile
    def add_skill(self, provider_id: str, skill_id: str, proficiency: float, category: str) -> None
    def set_location(self, provider_id: str, city, country, timezone, is_remote) -> None
    def set_pricing(self, provider_id: str, hourly_rate: float, currency: str) -> None
    def set_availability(self, provider_id: str, availability: dict) -> None
    def compute_completeness(self, provider_id: str) -> dict   # 返回 score + missing_fields
    def verify(self, provider_id: str) -> None                 # Ed25519 验证通过后置 is_verified
    def search(self, query, skill, city, country, max_rate,
               category, page, page_size) -> list[ProviderProfile]  # 排序见 6.3
    def record_booking(self, provider_id: str, rating: float | None = None) -> None
```

### 6.2 BountyService（`market/bounties.py`）

```python
class BountyService:
    def __init__(self, db_session: Session): ...

    def create(self, poster_id: str, *, dry_run: bool = False, **fields) -> Bounty
    # dry_run=True 仅校验并返回预览，不落库（对应 RentAHuman create_bounty dryRun）
    def publish(self, bounty_id: str) -> Bounty                  # draft → open
    def search(self, query, category, skill, city, max_price, page, page_size) -> ...
    def apply(self, bounty_id: str, applicant_id: str, message: str) -> BountyApplication
    def accept_application(self, bounty_id: str, application_id: str) -> None
    def submit_delivery(self, bounty_id: str, evidence: dict) -> None      # → submitted
    def confirm_delivery(self, bounty_id: str, accepted: bool) -> None     # → work_completed / disputed
    def settle(self, bounty_id: str) -> SettlementResult                   # 复用 SettlementEngine
```

### 6.3 搜索排序（复用现有权重公式）

排序分复用 `DistributionEngine` 动态权重系数（历史 0.4 / 归因 0.3 / 成功率 0.2 / 治理 0.1），映射到供应方画像：

```
rank = 0.4 * (total_bookings 归一化) 
     + 0.3 * (当前周期已结算贡献)
     + 0.2 * success_rate 
     + 0.1 * governance_participation
```

新供应方冷启动：`success_rate=1.0` 兜底（与 `Contributor` 默认一致），`total_bookings=0` 时按「完整度 × 新鲜度」降级排序。

---

## 7. API 层设计（Phase C）

### 7.1 新增 `web_api/onboarding.py`

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/onboarding/register` | 选角色（provider/consumer/both），注册 Ed25519 身份 |
| POST | `/onboarding/verify` | challenge-response 身份验证 → `is_verified` |
| POST | `/onboarding/profile` | 创建/更新画像（技能/位置/定价/可用性） |
| GET | `/onboarding/profile/{provider_id}/completeness` | 完整度进度条 + 缺失字段 |
| GET | `/market/providers/search` | 按 skill/city/country/max_rate 搜索 |
| GET | `/market/providers/{provider_id}` | 供应方公开画像（不含电话/收款敏感字段） |
| POST | `/market/bounties` | 创建 bounty（支持 `dry_run=true` 预览） |
| GET | `/market/bounties` | 搜索 bounty |
| POST | `/market/bounties/{id}/apply` | 申请 |
| POST | `/market/bounties/{id}/applications/{app_id}/accept` | 接受申请 |
| POST | `/market/bounties/{id}/submit` | 回传 evidence |
| POST | `/market/bounties/{id}/confirm` | 验收确认 → 触发结算 |
| GET | `/market/bounties/{id}/settlements` | 复用 SettlementEngine 历史查询 |

### 7.2 接线修复 `web_api/protocol.py`

将 `list_identities` / `registry_search` 空壳改为读取真实数据：

- `GET /protocol/identities` → 返回已注册身份（脱敏：不含私钥/公钥全文，仅 `identity_id + role + verified`）；
- `GET /protocol/registry/search` → 委托 `ProviderRegistry.search`；
- `GET /protocol/providers` → 可搜索供应方（新增端点）。

---

## 8. 协议层设计（Phase D，概念）

暴露 `skillos-mcp` 风格的 REST 端点，让外部 AI Agent 通过 Ed25519 签名身份接入：

```
search_providers(skill, city, max_rate)
create_bounty(title, description, completion_criteria, evidence_types, price_type, price, dry_run)
accept_application(bounty_id, application_id)
submit_delivery(bounty_id, evidence)
confirm_delivery(bounty_id, accepted)
list_bounties(status, mine)
```

- 复用 `IdentityClient`（Ed25519 challenge-response + 签名）作为 Agent 身份——对应 RentAHuman 的 `/api/keys/register-identity`；
- 复用 `Remote Bridge`（`protocol/remote_control.py`）的心跳/远程命令通道；
- 本阶段仅设计，不做真实 MCP server 包。

---

## 9. 合规红线（继承交叉验证结论）

1. **不托管真实资金**：Bounty 结算走 `SettlementEngine` 记账（5/25/70），不实现 Escrow / Stripe / 加密货币；
2. **AI 不独立缔约**：Bounty 的 `poster_id` 必须是挂靠的人类/企业主体（provider/consumer），不设「AI 独立账户收款」路径；
3. **法币支付留给下游持牌方**：本仓库保持开源内核 + 协议算法定位，委托代征/银行代发由落地平台方承接；
4. **隐私最小化**：公开画像不含电话/收款/私钥；`phone`、`gender` 默认不进入公开搜索返回体。

---

## 10. 实施时间表

| 阶段 | 内容 | 预估 | 交付物 |
|------|------|------|--------|
| A | 数据层：3 张模型 + Alembic migration | 1 天 | `models.py` 扩展 + migration |
| B | 服务层：ProviderRegistry + BountyService | 2 天 | `market/providers.py` + `market/bounties.py` + 单元测试 |
| C | API 层：onboarding + market 端点 + protocol.py 接线 | 1 天 | `web_api/onboarding.py` + 修改 protocol.py + API 测试 |
| D | 协议层：skillos-mcp 端点（概念） | 2 天 | 协议适配 + 集成测试 |
| 终验 | 全量门禁 | 0.5 天 | `make audit` 通过 |

**总计：约 6.5 天**

## 11. 验收标准

- [x] Provider 注册 → 补全 → 完整度进度条 → 可被搜索 全流程测试通过；
- [x] `is_profile_complete` 计算正确，缺失字段提示完整；
- [x] Bounty 状态机 `draft→open→assigned→submitted→work_completed→paid` 全流程测试通过，含 `dry_run` 预览与 `disputed` 分支；
- [x] `web_api/protocol.py` 空壳接线，`/protocol/identities` 返回真实数据；
- [x] 全量测试通过（基线 1127 passed → **1265 passed**），`make audit` 门禁通过；
- [x] 无真实资金/加密货币相关代码引入。

---

## 12. 下一步规划

**已完成（2026-07-31）**：Phase A→D 全部落地，`make audit` 门禁通过（1265 passed / 覆盖率 88.53%）。落地细节见 §13。

**中期**：新增 `skills/physical-task-bridge/` 正交技能，把 Bounty 中「物理世界任务」外派到下游真人市场（RentAHuman 式平台），形成「AI 编排（SkillOS）→ 数字任务自有技能 / 物理任务外部市场」闭环。

**长期**：若 SkillOS 生态要承接真实法币结算，需另立持牌公司做平台层（ICP/EDI/委托代征/等保三级），SkillOS 内核保持纯协议不变。

---

## 13. 落地记录（2026-07-31）

| 阶段 | 交付物 | 验证 |
|------|--------|------|
| A 数据层 | `db/models.py` 新增 ProviderProfileModel / BountyModel / BountyApplicationModel；`migrations/versions/004_add_provider_profiles_bounties.py` | create_all ✅ / 004 干净 upgrade+downgrade ✅ / 幂等 ✅ / market 36 tests ✅ |
| B 服务层 | `market/providers.py`（ProviderRegistry）+ `market/bounties.py`（BountyService）+ 41 测试 | 41 passed ✅ |
| C API 层 | `web_api/onboarding.py`（register/verify/profile/completeness）+ `market/api.py` providers/bounties 端点 + `web_api/protocol.py` 接线 + 25 测试 | 25 passed ✅ |
| D 协议层 | `web_api/agent.py`（MCP 风格端点 + Ed25519 签名鉴权）+ 15 测试 | 15 passed ✅ |
| 终验 | `make audit` 门禁 | 1265 passed / 0 failed / 覆盖率 88.53% / ruff+bandit / 3 verify scripts PASS / pip-audit 0 vulns |

**关键修复**：
- `db/engine.py`：内存 SQLite 改用 `StaticPool`（否则 API 多请求跨连接丢表）。
- `security/message_signer.py`：HTTP 头名小写规范化时 `verify` 失败——改为大小写不敏感查找（生产级健壮性 bug）。
- `tests/test_verify_kb_version_sync.py`：过期版本断言 "0.5" → "0.6"（项目已升至 0.6.0-beta），清除此前遗留的唯一失败。
