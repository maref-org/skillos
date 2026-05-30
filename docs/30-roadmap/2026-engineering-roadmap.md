# SkillOS 2026 工程实施路线图

> 版本：v0.3.0 → v0.6.0  
> 日期：2026-05-27  
> 状态：规划中  
> 基于：全量审计报告 & OpenSkill Protocol v0.3 白皮书

---

## 1. 当前基线（v0.3.0）

### 1.1 已实现模块

| 模块 | 文件 | 完成度 |
|------|------|--------|
| 版本管理 | `skillos/version.py` | 100% |
| 分配引擎 | `skillos/distribution/engine.py` | 90% |
| Skill 注册中心 | `skillos/market/registry.py` | 85% |
| 拜占庭共识 | `skillos/collaboration/consensus.py` | 80% |
| 身份客户端 | `skillos/protocol/identity_client.py` | 85% |
| 审计日志 | `skillos/audit.py` | 80% |
| 可观测性 | `skillos/observability/metrics.py` `tracing.py` | 75% |
| 数据库模型 | `skillos/db/models.py` | 90% |
| 数据仓库 | `skillos/db/repository.py` | 85% |

### 1.2 关键缺失（审计发现）

- **NegMarket**：白皮书完整设计，代码零实现
- **Men0 协议**：`skillos-contrib/openhuman/men0-interop/SKILL.md` 有文档，无 Python 代码
- **CSWDP**：`skillos-contrib/openhuman/openhuman-cswdp/SKILL.md` 有文档，无集成

---

## 2. 路线图概览

```
v0.3.0 (当前) ──→ v0.4.0 ──→ v0.5.0 ──→ v0.6.0
   Beta           Beta         RC           GA

时间轴：2026-Q2 ──→ 2026-Q3 ──→ 2026-Q4
```

| 版本 | 核心目标 | 关键交付物 |
|------|---------|-----------|
| **v0.4.0** | NegMarket MVP | 脱敏存储 + 反模式 Skill 生成 |
| **v0.5.0** | Men0 协议核心 | AgentCard + 消息路由 + 心跳 |
| **v0.6.0** | CSWDP 集成 | 生存保障金计算 + 成本熔断接口 |

---

## 3. v0.4.0 — NegMarket MVP（6-8 周）

### 3.1 目标

实现负样本市场的最小可用版本，支持：
1. 负样本的脱敏上传与加密存储
2. 反模式 Skill 的自动生成
3. 调用时动态脱敏输出

### 3.2 技术方案

#### 3.2.1 新增模块

```
skillos/negmarket/
├── __init__.py
├── desensitizer.py      # 四步脱敏流水线
├── storage.py           # 加密分片存储
├── anti_pattern.py      # 反模式生成器
├── zk_verifier.py       # 零知识验证（模拟）
├── api.py               # FastAPI 路由
└── models.py            # 数据库模型扩展
```

#### 3.2.2 数据库变更（Alembic Migration）

```python
# migrations/versions/005_add_negmarket.py
class NegativeSampleModel(Base):
    __tablename__ = "negative_samples"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    contributor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    original_hash: Mapped[str] = mapped_column(String(128), nullable=False)  # SHA-256
    encrypted_blob: Mapped[str] = mapped_column(Text, nullable=False)        # AES-256-GCM
    desensitized_pattern: Mapped[dict] = mapped_column(JSON, default=dict)   # 结构化反模式
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), default="medium")
    verification_status: Mapped[str] = mapped_column(String(32), default="pending")
    price_per_call: Mapped[float] = mapped_column(Float, default=0.1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

class AntiPatternSkillModel(Base):
    __tablename__ = "anti_pattern_skills"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sample_id: Mapped[str] = mapped_column(ForeignKey("negative_samples.id"), nullable=False)
    skill_manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_by: Mapped[str] = mapped_column(String(128), nullable=False)  # Agent ID
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
```

#### 3.2.3 脱敏流水线实现

```python
# skillos/negmarket/desensitizer.py
class DesensitizationPipeline:
    """四步脱敏流水线"""

    STEP_1_LOCAL_PII = "local_pii"
    STEP_2_ZK_VERIFY = "zk_verify"
    STEP_3_SKILL_GENERATE = "skill_generate"
    STEP_4_DYNAMIC_MASK = "dynamic_mask"

    def process(self, raw_text: str, contributor_id: str) -> NegativeSample:
        # Step 1: 本地 PII 识别 + 替换（Gemma 4 本地模型）
        desensitized = self._local_pii_replace(raw_text)

        # Step 2: 零知识验证（HMAC-SHA256 承诺）
        proof = self._zk_verify(desensitized, contributor_id)

        # Step 3: 反模式 Skill 生成
        anti_pattern = self._generate_anti_pattern_skill(desensitized)

        # Step 4: 调用时动态脱敏（二次扫描 + 差分隐私）
        return NegativeSample(
            original_hash=sha256(raw_text.encode()).hexdigest(),
            encrypted_blob=self._encrypt(raw_text, contributor_id),
            desensitized_pattern=desensitized,
            anti_pattern_skill=anti_pattern,
            zk_proof=proof,
        )
```

#### 3.2.4 API 接口

```python
# skillos/negmarket/api.py
@router.post("/negmarket/upload")
async def upload_negative_sample(
    raw_text: str,
    category: str,
    contributor_id: str,
    current_user: IdentityRecord = Depends(get_current_user),
):
    """上传负样本（经过四步脱敏）"""
    ...

@router.post("/negmarket/{sample_id}/call")
async def call_anti_pattern(
    sample_id: str,
    business_params: dict,
    current_user: IdentityRecord = Depends(get_current_user),
):
    """调用反模式 Skill（仅输出风险等级 + 抽象警告）"""
    ...

@router.get("/negmarket/discover")
async def discover_anti_patterns(
    category: str | None = None,
    risk_level: str | None = None,
    sort: str = "relevance",
):
    """发现反模式 Skill（可用不可看）"""
    ...
```

### 3.3 验收标准

- [ ] 负样本上传后原始文本不可通过 API 获取
- [ ] 反模式 Skill 调用仅返回风险等级、抽象警告、反模式 ID
- [ ] 贡献者可下载自己的解密密钥（本地持有）
- [ ] 集成到 5/25/70 分配引擎（NegMarket 收益计入生态基金）
- [ ] pytest 覆盖率 >= 80%

### 3.4 依赖

- `cryptography>=42.0.0`（已有）
- 新增可选：`presidio-analyzer>=2.2`（PII 识别）

---

## 4. v0.5.0 — Men0 协议核心（8-10 周）

### 4.1 目标

实现 Men0 协议核心，支持 Agent 间通信、发现与协调：
1. AgentCard 注册与发现
2. JSONL 消息路由
3. 心跳检测与生命周期管理

### 4.2 技术方案

#### 4.2.1 新增模块

```
skillos/men0/
├── __init__.py
├── agent_card.py        # AgentCard 定义与验证
├── message_router.py    # JSONL 消息路由
├── discovery.py         # Agent 发现服务
├── heartbeat.py         # 心跳检测
├── gateway.py           # 五协议网关兼容层
├── api.py               # FastAPI 路由
└── models.py            # 数据库模型扩展
```

#### 4.2.2 核心数据结构

```python
# skillos/men0/agent_card.py
@dataclass
class AgentCard:
    agent_id: str
    capabilities: list[str]
    skills: list[str]
    identity: dict[str, Any]
    endpoint: str  # /.well-known/agent-card.json
    registered_at: float
    last_heartbeat: float
    status: str  # active / inactive / suspended

# skillos/men0/message_router.py
@dataclass
class Men0Message:
    type: str  # task_create / message / status_update / artifact
    msg_id: str
    from_agent: str
    to_agent: str | None  # None = broadcast
    payload: dict[str, Any]
    timestamp: float
```

#### 4.2.3 文件系统原生方案

```python
# skillos/men0/message_router.py
class JSONLMessageRouter:
    """JSONL 文件系统原生消息路由（flock + inotify）"""

    BASE_PATH = Path("/var/men0")

    def send(self, msg: Men0Message) -> None:
        task_file = self.BASE_PATH / "tasks" / f"{msg.msg_id}.jsonl"
        lock_file = task_file.with_suffix(".jsonl.lock")

        # 原子写入
        cmd = f'flock {lock_file} -c \'echo "{msg.to_json()}" >> {task_file}\''
        subprocess.run(cmd, shell=True, check=True)

    def watch(self, task_id: str) -> Iterator[Men0Message]:
        """实时流监控（inotifywait）"""
        task_file = self.BASE_PATH / "tasks" / f"{task_id}.jsonl"
        process = subprocess.Popen(
            ["inotifywait", "-m", "-e", "modify", str(task_file)],
            stdout=subprocess.PIPE,
            text=True,
        )
        for line in iter(process.stdout.readline, ""):
            yield self._parse_last_line(task_file)
```

#### 4.2.4 五协议网关兼容

```python
# skillos/men0/gateway.py
class ProtocolGateway:
    """五协议网关兼容层"""

    SUPPORTED_PROTOCOLS = ["a2a", "mcp", "acp", "anp", "awcp"]

    def convert_to_men0(self, msg: dict, protocol: str) -> Men0Message:
        if protocol == "a2a":
            return self._a2a_to_men0(msg)
        elif protocol == "mcp":
            return self._mcp_to_men0(msg)
        ...

    def convert_from_men0(self, msg: Men0Message, protocol: str) -> dict:
        ...
```

#### 4.2.5 API 接口

```python
# skillos/men0/api.py
@router.post("/men0/agents/register")
async def register_agent(card: AgentCard):
    """注册 AgentCard"""
    ...

@router.get("/men0/agents/discover")
async def discover_agents(
    capability: str | None = None,
    skill: str | None = None,
):
    """发现 Agent"""
    ...

@router.post("/men0/messages/send")
async def send_message(msg: Men0Message):
    """发送消息"""
    ...

@router.get("/men0/messages/watch/{task_id}")
async def watch_messages(task_id: str):
    """SSE 实时流"""
    ...

@router.post("/men0/agents/heartbeat")
async def agent_heartbeat(agent_id: str):
    """心跳检测"""
    ...
```

### 4.3 验收标准

- [ ] AgentCard 可注册、可发现、可验证
- [ ] JSONL 消息路由支持 flock 原子写入
- [ ] 心跳检测自动标记 inactive Agent
- [ ] A2A 协议原生兼容（Google Agent-to-Agent）
- [ ] SSE 实时流支持 1000+ 并发连接
- [ ] pytest 覆盖率 >= 80%

### 4.4 依赖

- 新增：`watchdog>=3.0`（inotify 跨平台封装）
- 新增：`sse-starlette>=2.0`（SSE 支持）

---

## 5. v0.6.0 — CSWDP 集成（6-8 周）

### 5.1 目标

集成 CSWDP（Carbon-Silicon Wisdom Dividend Protocol），实现：
1. 生存保障金计算接口
2. 成本熔断机制
3. 质量门禁自动化

### 5.2 技术方案

#### 5.2.1 新增模块

```
skillos/cswdp/
├── __init__.py
├── survival_fund.py     # 生存保障金计算
├── cost_circuit.py      # 成本熔断
├── quality_gate.py      # 质量门禁
├── api.py               # FastAPI 路由
└── models.py            # 数据库模型扩展
```

#### 5.2.2 生存保障金计算

```python
# skillos/cswdp/survival_fund.py
class SurvivalFundCalculator:
    """生存保障金计算引擎"""

    def calculate(
        self,
        contributor_id: str,
        historical_contribution: float,
        current_period_revenue: float,
        skill_success_rate: float,
        governance_participation: float,
    ) -> SurvivalFundRecord:
        """
        计算公式：
        基础保障 = 当地最低工资 × 1.5
        贡献加成 = 基础保障 × (历史贡献度 × 0.4 + 成功率 × 0.3 + 治理参与 × 0.3)
        上限 = 基础保障 × 3.0
        """
        base = self._local_min_wage * 1.5
        bonus = base * (
            historical_contribution * 0.4 +
            skill_success_rate * 0.3 +
            governance_participation * 0.3
        )
        amount = min(base + bonus, base * 3.0)

        return SurvivalFundRecord(
            contributor_id=contributor_id,
            base_amount=base,
            bonus_amount=bonus,
            total_amount=amount,
            period=self._current_period(),
        )
```

#### 5.2.3 成本熔断机制

```python
# skillos/cswdp/cost_circuit.py
class CostCircuitBreaker:
    """成本熔断器"""

    MODES = {
        "NORMAL": (0.30, float("inf")),    # >30% 预算剩余
        "LOW": (0.10, 0.30),               # 10-30%
        "CRITICAL": (0.02, 0.10),          # 2-10%
        "PAUSED": (0.0, 0.02),             # <2%
    }

    def __init__(self, daily_budget_usd: float = 5.0):
        self.daily_budget = daily_budget_usd
        self.spent_today = 0.0

    def check(self, estimated_cost: float) -> dict:
        remaining_pct = 1.0 - (self.spent_today / self.daily_budget)
        mode = self._get_mode(remaining_pct)

        if mode == "PAUSED":
            return {"allowed": False, "mode": mode, "reason": "budget_exhausted"}
        if mode == "CRITICAL" and estimated_cost > self.daily_budget * 0.02:
            return {"allowed": False, "mode": mode, "reason": "cost_too_high"}

        return {"allowed": True, "mode": mode, "remaining_pct": remaining_pct}
```

#### 5.2.4 质量门禁

```python
# skillos/cswdp/quality_gate.py
class QualityGate:
    """质量门禁自动化"""

    CHECKS = {
        "ruff": "ruff check .",
        "mypy": "mypy --strict skillos/",
        "pytest": "pytest --cov=skillos --cov-report=term-missing",
        "bandit": "bandit -r skillos/",
        "pip_audit": "pip-audit",
    }

    THRESHOLDS = {
        "pytest_coverage": 0.80,
    }

    def run_all(self) -> QualityReport:
        results = {}
        for name, cmd in self.CHECKS.items():
            results[name] = self._run_check(name, cmd)
        return QualityReport(results=results, passed=all(r["passed"] for r in results.values()))
```

#### 5.2.5 API 接口

```python
# skillos/cswdp/api.py
@router.post("/cswdp/survival-fund/calculate")
async def calculate_survival_fund(contributor_id: str):
    """计算生存保障金"""
    ...

@router.get("/cswdp/cost-circuit/status")
async def get_cost_circuit_status():
    """获取成本熔断状态"""
    ...

@router.post("/cswdp/quality-gate/run")
async def run_quality_gate():
    """运行质量门禁"""
    ...
```

### 5.3 验收标准

- [ ] 生存保障金计算接口返回正确金额
- [ ] 成本熔断在预算 <2% 时自动暂停调用
- [ ] 质量门禁集成 ruff / mypy / pytest / bandit / pip-audit
- [ ] 五层设计模式（L1-L5）状态可查询
- [ ] pytest 覆盖率 >= 80%

### 5.4 依赖

- 已有：`ruff>=0.15.0`, `mypy>=1.0.0`, `pytest>=7.0.0`, `bandit>=1.7.0`, `pip-audit>=2.0.0`

---

## 6. 通用工程规范

### 6.1 版本管理

```python
# skillos/version.py（每个版本更新）
__version__ = "0.4.0"  # NegMarket MVP
__version__ = "0.5.0"  # Men0 协议核心
__version__ = "0.6.0"  # CSWDP 集成
```

### 6.2 数据库迁移

每个版本独立 Alembic migration：

```bash
alembic revision -m "add_negmarket_tables"      # v0.4.0
alembic revision -m "add_men0_protocol_tables"  # v0.5.0
alembic revision -m "add_cswdp_tables"          # v0.6.0
```

### 6.3 测试策略

```
tests/
├── test_negmarket/
│   ├── test_desensitizer.py
│   ├── test_storage.py
│   └── test_api.py
├── test_men0/
│   ├── test_agent_card.py
│   ├── test_message_router.py
│   └── test_gateway.py
└── test_cswdp/
    ├── test_survival_fund.py
    ├── test_cost_circuit.py
    └── test_quality_gate.py
```

### 6.4 文档更新

每个版本更新：
- `docs/05-api.md` — API 文档
- `docs/04-development.md` — 开发指南
- `CHANGELOG.md` — 变更日志

---

## 7. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| NegMarket 脱敏算法误杀率高 | P1 | 先内测 100 条样本，调优阈值 |
| Men0 JSONL 性能瓶颈 | P2 | 预留 Redis Stream 升级路径 |
| CSWDP 法律合规 | P1 | 咨询深圳龙岗 OPC 法务 |
| 贡献者隐私泄露 | P0 | 加密密钥本地持有，平台不存储 |

---

## 8. 附录

### 8.1 参考文档

- [OpenSkill Protocol v0.3 白皮书](/Volumes/1TB-M2/Athena知识库/执行项目/2026/003-open human（碳硅基共生）/021-战略与商业/OpenSkill_Protocol_白皮书_v0.3-20260517.md)
- [Men0 互操作协议 SKILL.md](/Volumes/1TB-M2/public/skillos/skillos-contrib/openhuman/men0-interop/SKILL.md)
- [CSWDP 主权数字化工厂协议 SKILL.md](/Volumes/1TB-M2/public/skillos/skillos-contrib/openhuman/openhuman-cswdp/SKILL.md)
- [SkillOS 架构设计](/Volumes/1TB-M2/Athena知识库/OPC工作区/2-战略/SkillOS操作系统/01-核心文档/03-架构设计.md)

### 8.2 关键人员

- 技术负责人：SkillOS Team
- 产品负责人：OpenHuman 项目组
- 法务合规：深圳龙岗 OPC

---

*本文档由全量审计报告驱动，每个版本完成后需进行审计验证。*
