# M6 设计：持牌支付 manifest 对接 + 真实外部 Agent 接入 + 垂直场景上线内测

> 上位法：受 [Athena 系统宪法 v1.5](../../CONSTITUTION.md) 与 [SkillOS 治理框架](../../GOVERNANCE.md) 约束。
> 前置：M5 已落地出款指令记账层（`PayoutService` + `GET /outcome/payouts/{contract_id}` + `external_agent_demo.py`）。

## 1. 背景与目标

M5 打通了「结算 → 出款指令记账」链路，但仍是 `TestClient` 模拟 + 纯记账 JSON，未接通真实持牌支付通道，也未让外部 Agent 用真实 HTTP + 签名接入。M6 目标：

1. **持牌支付 manifest 对接**：定义 `PaymentProvider` 抽象接口，提供支付宝 / 微信支付双平台 adapter（无真实 key 自动降级 sandbox），接收持牌平台 webhook 回调并回写 `mark_executed`。
2. **真实外部 Agent 接入**：把 demo 从 `TestClient` 换成真实 `uvicorn` HTTP 服务，外部 Agent 用真实 HTTP + Ed25519 签名跑通完整链路。
3. **垂直场景上线内测**：内容 IP 代运营场景产品化——场景化需求模板 + 内测 CLI + 一键演示。

**红线（继承）**：§9 不托管真实资金。adapter 只做「提交出款指令 → 查询状态 → 接收回执」的协议对接；真实法币划转由持牌平台执行。无 key 环境一律走 sandbox，绝不用测试 key 冒充真实交易。

## 2. 现状与差距（交叉验证要点）

| 能力 | 现状 | M6 差距 |
|------|------|---------|
| 出款指令 | `PayoutService.export_manifest` 纯记账 JSON | 需可被持牌平台 adapter 消费的标准化载荷 |
| 平台对接 | 无 | 需 `PaymentProvider` 抽象 + Alipay/WeChat adapter + sandbox |
| 回执处理 | `mark_executed(instruction_id, external_ref)` 手动调用 | 需 webhook 端点自动回写 |
| Agent 接入 | `TestClient` 模拟 | 需真实 uvicorn 服务 + 真实 HTTP 签名客户端 |
| 垂直场景 | 散在测试/脚本 | 需场景化模板 + 内测 CLI |

## 3. 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                 SkillOS 记账层（不托管资金）              │
│  PayoutService.export_manifest(contract_id)             │
└───────────────────────────┬─────────────────────────────┘
                            │ 标准化 manifest 载荷
                            ▼
┌─────────────────────────────────────────────────────────┐
│            PaymentProvider 抽象接口（skillos/market/payments/）│
│  submit_manifest(manifest) -> ProviderPaymentRef        │
│  query_status(ref) -> ProviderStatus                    │
│  verify_webhook(headers, body) -> instruction_ids       │
│  (无 key 环境自动选择 sandbox 实现)                       │
├─────────────────────────────────────────────────────────┤
│  AlipayProvider   │  WeChatPayProvider  │  SandboxProvider│
│  (开放平台沙箱)   │  (v3 沙箱)          │  (本地模拟)    │
└──────────────┬──────────┬──────────────┬────────────────┘
               ▼          ▼              ▼
         支付宝沙箱网关  微信支付沙箱   本地模拟回执
               └───────── webhook 回调 ─┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│   webhook 端点：POST /payments/webhooks/{provider}      │
│   验签 → 回写 PayoutService.mark_executed()             │
└─────────────────────────────────────────────────────────┘
```

**真实 Agent 接入拓扑**：

```
外部 Agent（真实 HTTP 客户端）
   │  Ed25519 签名头（X-Signer-Id / X-Signature / X-Timestamp / X-Public-Key）
   ▼
uvicorn 运行的真实 SkillOS 服务（skillos.app:app）
   ├── /agent/*       MCP 风格端点（已有）
   ├── /outcome/*     成果契约闭环（已有）
   └── /payments/*    M6 新增
```

## 4. 组件设计

### 4.1 `skillos/market/payments/base.py` — PaymentProvider 抽象

```python
@dataclass
class ProviderPaymentRef:
    provider: str          # "alipay" | "wechat" | "sandbox"
    external_ref: str      # 持牌平台侧流水号
    status: str            # "submitted" | "processing" | "succeeded" | "failed"

class PaymentProvider(Protocol):
    name: str
    def submit_manifest(self, manifest: dict) -> ProviderPaymentRef: ...
    def query_status(self, external_ref: str) -> ProviderStatus: ...
    def verify_webhook(self, headers: dict, body: dict) -> list[str]: ...  # 返回 instruction_ids

def get_provider(name: str = "") -> PaymentProvider:
    """工厂：环境变量 SKILLOS_PAYMENT_PROVIDER 指定，未配置/无 key → SandboxProvider。"""
```

### 4.2 双平台 adapter + sandbox

- `alipay.py`: 支付宝开放平台沙箱对接。用 `SKILLOS_ALIPAY_APP_ID` / `SKILLOS_ALIPAY_PRIVATE_KEY`（RSA2），未配置 → 抛 `ProviderNotConfigured` 由工厂降级 sandbox。测试用官方沙箱网关 URL。
- `wechat.py`: 微信支付 v3 沙箱。用 `SKILLOS_WECHAT_MCH_ID` / `SKILLOS_WECHAT_APIV3_KEY`，未配置 → 降级 sandbox。
- `sandbox.py`: 本地模拟。`submit_manifest` 生成 `sandbox-{uuid}` 流水号并 `mark_executed` 到每条指令（保持 DB 幂等）；`verify_webhook` 校验固定 HMAC 测试密钥。**默认实现，保证无 key 环境全链路可测。**

### 4.3 `skillos/market/payments/webhook.py` — 回执回写

`POST /payments/webhooks/{provider}`：
- 接收持牌平台回调载荷（headers + body）
- 调 `provider.verify_webhook(headers, body)` 验签
- 对返回的 instruction_ids 逐个 `PayoutService.mark_executed(instruction_id, external_ref)`
- 验签失败 → 401；未知 provider → 404

### 4.4 `skillos/market/payments/__init__.py` — 组装

- 工厂 `get_provider()` + 便利方法 `submit_contract_payout(contract_id)`（调 export_manifest → submit_manifest → 回写）。
- router 挂载到 `web_api/__init__.py`。

### 4.5 真实服务接入

- 新增 `scripts/run_server.py`：`uvicorn skillos.app:app` 启动真实服务（含 `--port`）。
- 新增 `scripts/agent_http_client.py`：真实外部 Agent 的 HTTP 客户端封装（Ed25519 签名 + httpx 调用），替代 `TestClient`。
- 改造 `external_agent_demo.py` 支持 `--real-server` 模式走真实 HTTP。

### 4.6 垂直场景内测

- 新增 `skillos/scenarios/`（或沿用 `docs/scenarios/`）内容 IP 代运营场景包：
  - `ip_operations.py`: 场景化需求模板（企业主意图 → 结构化需求文本）+ 拆解交付物预设
  - 内测 CLI `scripts/ip_operations_trial.py`：一键跑「真实 HTTP + 真实支付 sandbox + 内容 IP 代运营」端到端 = GO/NO-GO
- 需求模板接入 `OutcomeContractService.create` 的 rule-based 拆解（复用 M1 内容 IP 垂直场景）。

## 5. 数据层

- 无新表。`PayoutInstructionModel.external_ref` 存持牌平台流水号（sandbox 时存 `sandbox-{uuid}`）。
- `status` 复用现有枚举：`pending → executed`（webhook 回写）。

## 6. API 一览（M6 新增）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/payments/webhooks/{provider}` | 持牌平台回执回调（验签 → mark_executed） |
| GET  | `/payments/providers` | 列出当前可用 provider 与配置状态（只读） |
| POST | `/payments/contracts/{id}/submit` | 手动触发出款提交到持牌平台（签名，非 require — 记账层内部触发为主） |

## 7. 测试计划

- `tests/test_payment_provider.py`：抽象 + 工厂降级（无 key → sandbox）+ sandbox submit/query/webhook 验签
- `tests/test_payment_webhook.py`：webhook 端点验签成功回写 / 验签失败 401 / 未知 provider 404
- `tests/test_alipay_adapter.py`：RSA2 签名构造 + 无 key 抛 `ProviderNotConfigured` + 沙箱 URL 请求构造（httpx mock）
- `tests/test_wechat_adapter.py`：v3 签名头构造 + 无 key 降级
- `tests/test_agent_http_client.py`：真实 httpx 客户端签名 + TestClient 跑通（等价真实 HTTP）
- `scripts/ip_operations_trial.py` 作为 e2e 冒烟（不入 pytest 或标记慢）

## 8. 红线确认

1. **不托管真实资金**（§9）：无 Escrow；adapter 只提交记账指令；无 key 一律 sandbox，绝不假造真实交易。
2. **AI 不独立缔约**（§8.2）：契约方仍强制签名身份。
3. **密钥不入库**：adapter 密钥仅从环境变量读取，测试用 sandbox 密钥写死在测试文件（非生产凭据）。

## 9. 里程碑

| 里程碑 | 内容 | 验收 |
|--------|------|------|
| M6-P1 | PaymentProvider 抽象 + Sandbox + 双平台 adapter（无 key 降级） | 工厂降级测试全绿 |
| M6-P2 | webhook 回写端点 + 手动提交端点 + API 挂载 | webhook 测试全绿 |
| M6-P3 | 真实 uvicorn 服务 + HTTP 签名客户端 + demo 改造 | `--real-server` 模式端到端 GO |
| M6-P4 | 内容 IP 代运营垂直场景包 + 内测 CLI | 一键内测 GO |

## 10. 落地记录

- 2026-08-01: 设计定稿。范围确认：双平台 adapter（支付宝 + 微信沙箱）+ 真实服务接入 + 内容 IP 代运营垂直场景内测 CLI。红线内：无 key 一律 sandbox。
- 2026-08-01: **M6 全部落地完成**，`make audit` 全绿（1346 passed, 1 skipped, coverage 88.77%, ruff 0 问题, 3 verify scripts PASS）。
  - **P1 抽象层**: `skillos/market/payments/` — `base.py`（`PaymentProvider` 协议 + `ProviderPaymentRef`/`ProviderStatus`/`ProviderNotConfiguredError` + `get_provider()` 工厂）+ `sandbox.py`（本地模拟持牌支付，无 key 默认）+ `alipay.py`（RSA2 签名 + `alipay.fund.trans.uni.transfer` 沙箱载荷）+ `wechat.py`（v3 HMAC-SHA256 签名 + 转账沙箱载荷）+ `submit_contract_payout()`（出款 → 提交 → 回写 external_ref）+ 21 测试。
  - **P2 webhook 层**: `web_api/payments.py` — `GET /payments/providers`（配置状态只读）、`POST /payments/webhooks/{provider}`（验签 → mark_executed 回写）、`POST /payments/contracts/{id}/submit`（手动出款提交）+ 8 测试。
  - **P3 真实服务接入**: `scripts/run_server.py`（uvicorn 真实服务）+ `scripts/agent_http_client.py`（外部 Agent HTTP 客户端）+ `MessageSigner.sign_headers_http()`（X-Public-Key base64url 编码，HTTP 头不允许换行）+ `verify()` 兼容解码。`external_agent_demo.py` 支持 `--real-server` 真实 HTTP 端到端 GO + 2 测试。
  - **P4 垂直场景**: `skillos/scenarios/ip_operations.py`（`IpTrialScenario` + 3 个模板：内容代运营/短视频矩阵/知识付费专栏）+ `scripts/ip_operations_trial.py`（一键内测 CLI，内置/真实双模式，GO/NO-GO）+ 6 测试。
  - **关键踩坑**: HTTP 头不能含换行 → X-Public-Key 必须 base64url 编码（httpx 报 `Illegal header value`）；磁盘 SQLite 旧 schema 会因 `create_all` 不加列而报 `no column named base_price`（删旧库重建）；ASGI transport 在 httpx 0.28 只有异步 `handle_async_request`（需 AsyncClient）；N818 异常命名需 Error 后缀。
