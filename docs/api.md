# SkillOS API 文档

## 核心模块

### SkillKernel

Skill 生命周期管理核心。

```python
from skillos import SkillKernel

kernel = SkillKernel()
```

#### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `distill` | `(source: str) -> SkillManifest` | 从 GitHub URL 蒸馏 Skill |
| `mint_nft` | `(manifest: SkillManifest) -> NFTRecord` | 铸造 Skill NFT |
| `assemble_tools` | `(nft: NFTRecord) -> ToolChain` | 组装工具链 |
| `execute` | `(skill_id: str, inputs: dict) -> ExecutionResult` | 执行 Skill |

### DistributionEngine

5/25/70 经济分配引擎。

```python
from skillos import DistributionEngine

engine = DistributionEngine()
```

#### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `allocate` | `(amount: Decimal, skill_id: str) -> AllocationResult` | 单笔收入分配 |
| `register_contributor` | `(skill_id: str, contributor: Contributor) -> None` | 注册贡献者 |
| `settle` | `(period: SettlementPeriod) -> SettlementResult` | 周期结算 |

### SessionManager

会话生命周期管理。

```python
from skillos import SessionManager

mgr = SessionManager()
```

#### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `create` | `(user_id: str) -> Session` | 创建会话 |
| `add_item` | `(session_id: str, item: SessionItem) -> None` | 添加项目 |
| `pause` | `(session_id: str) -> None` | 暂停会话 |
| `resume` | `(session_id: str) -> None` | 恢复会话 |
| `complete` | `(session_id: str) -> None` | 完成会话 |

## 协议客户端

### RegistryClient

```python
from skillos.protocol import RegistryClient

client = RegistryClient(base_url="https://registry.skillos.dev")
client.register(skill_manifest)
client.discover(query="image-generation")
```

### MatcherClient

```python
from skillos.protocol import MatcherClient

client = MatcherClient(base_url="https://matcher.skillos.dev")
client.match(intent="generate image of a cat")
```

### SettlementClient

```python
from skillos.protocol import SettlementClient

client = SettlementClient(base_url="https://settlement.skillos.dev")
client.settle(period="weekly")
```

### IdentityClient

```python
from skillos.protocol import IdentityClient

client = IdentityClient()
client.sign(data=b"payload")
client.verify_identity(challenge, response)
```

## 可观测性

### Metrics

```python
from skillos.observability.metrics import metrics

@metrics.timed("/api/execute")
def handle_execute(request):
    metrics.counter("skillos_skill_executions_total", labels={"skill_id": "xxx"})
    ...
```

### Tracing

```python
from skillos.observability.tracing import tracer

with tracer.span("process_request") as span:
    span.set_attribute("user_id", user_id)
    ...
```

### Logging

```python
from skillos.observability.logging_config import get_logger

logger = get_logger("skillos.kernel")
logger.info("skill_executed", skill_id="xxx", duration_ms=120)
```

## 功能开关

```python
from skillos.feature_flags import FeatureFlagManager, FlagType, FlagState

mgr = FeatureFlagManager()
mgr.create_flag("new_ui", FlagType.BOOLEAN, FlagState.ROLLOUT, value=True)

if mgr.is_enabled("new_ui", user_id="user-123"):
    ...
```

## 错误码

| Code | Meaning | HTTP Status |
|------|---------|-------------|
| `VALIDATION_ERROR` | 参数校验失败 | 400 |
| `AUTHENTICATION_ERROR` | 认证失败 | 401 |
| `AUTHORIZATION_ERROR` | 权限不足 | 403 |
| `NOT_FOUND` | 资源不存在 | 404 |
| `RATE_LIMITED` | 请求频率超限 | 429 |
| `INTERNAL_ERROR` | 内部错误 | 500 |
| `SERVICE_UNAVAILABLE` | 服务不可用 | 503 |
