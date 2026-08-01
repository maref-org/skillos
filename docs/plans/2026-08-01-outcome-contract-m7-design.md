# M7 设计：支付协议完备 + 真实沙箱对接 + 外部 Agent 内测 + 垂直场景多租户

> 上位法：受 [Athena 系统宪法 v1.5](../../CONSTITUTION.md) 与 [SkillOS 治理框架](../../GOVERNANCE.md) 约束。
> 前置：M6 已落地支付抽象层 + webhook + 真实服务 + 垂直场景（`make audit` 全绿，1346 passed）。
> 同步方向：A→B 单向（Athena 开发源 → GitHub 发布源），发布前须经叙事转化引擎。

## 1. 背景与目标

M6 打通了「结算 → 出款指令 → 持牌 adapter（无 key 降级 sandbox）→ webhook 回写」全链路，且真实 uvicorn + HTTP 签名端到端 GO。M7 按 4 个方向收尾商业验证的「协议完备性 + 真实对接 + 规模化内测」：

1. **支付协议完备性补齐**（P1，前置基础）：修复 M6 review 遗留的 3 个语义缺口 ——
   - `webhook` 端点从 body 顶层取 `external_ref`（`web_api/payments.py:73`），而真实平台回执字段是 `out_biz_no`（支付宝）/ `out_bill_no`（微信）→ 需 `verify_webhook` 协议携带回执单号并做字段映射。
   - 支付宝 webhook 无公钥 RSA2 验签（当前仅字段级校验）。
   - 微信 v3 请求签名是 HMAC-SHA256 模拟（当前 scheme 声称 RSA2048 但算法是 HMAC），需支持真实商户证书 RSA-SHA256。
2. **真实支付沙箱对接验证**（P2，依赖 P1）：新增验证脚本，配置持牌方测试 key 时跑真实沙箱网关对接，无 key 时 SKIP（不失败）。
3. **外部 Agent 真实接入内测**（P3）：新增 HTTP 组队端点（当前真实模式 `_seed_team` 直接跳过组队）、心跳循环/断线重连/多客户端并发内测。
4. **垂直场景多租户上线**（P4）：引入轻量租户模型 + 场景包按租户配置 + 多租户并发内测 + 运营看板。

**红线（继承）**：§9 不托管真实资金；§8.2 AI 不独立缔约（contractor 强制签名身份）；密钥只从环境变量读取、不入库。

## 2. 现状与差距（交叉验证要点）

| 能力 | 现状 | M7 差距 |
|------|------|---------|
| webhook 回执单号 | `body.get("external_ref")` 顶层取（sandbox 自定义字段） | 需协议携带 `external_ref` + adapter 映射真实字段（out_biz_no / out_bill_no） |
| 支付宝验签 | 仅字段级校验（app_id/notify_type/status） | 需支付宝公钥 RSA2 验签（可选配置，未配置降级字段校验） |
| 微信 v3 签名 | HMAC-SHA256 模拟（scheme 声称 RSA2048） | 需商户证书 RSA 私钥 RSA-SHA256 真实签名（可选配置，未配置保留 HMAC） |
| 真实沙箱对接 | 无 key 一律 sandbox | 需 `verify_payment_sandbox.py`：有 key 跑真实沙箱，无 key SKIP |
| 外部 Agent 组队 | `create_service_team` 服务层直调（无 HTTP 端点） | 需 `POST /agent/contracts/{id}/team` |
| 心跳/长连接 | `RemoteBridge` 纯内存、无过期回收 | 需心跳过期回收 + 断线重连 |
| 多客户端并发 | 单客户端演示 | 需多 Agent 并发内测 |
| 多租户 | 全库无 tenant 概念 | 需 `TenantModel` + `outcome_contracts.tenant_id` + 场景包按租户配置 + 运营看板 |

## 3. 架构设计

```
                    ┌────────────────────────────────────────────┐
                    │             SkillOS 记账层（不托管资金）      │
                    │  PayoutService.export_manifest(contract_id) │
                    └──────────────┬─────────────────────────────┘
                                   │ 标准化 manifest
                                   ▼
        ┌────────────────────────────────────────────────────────┐
        │  PaymentProvider 协议（M7 扩展 verify_webhook 返回      │
        │  WebhookReceipt: instruction_ids + external_ref）      │
        ├───────────────────────────┬────────────────────────────┤
        │  AlipayProvider           │  WeChatPayProvider         │
        │  · RSA2 请求签名（已有）   │  · HMAC 沙箱签名（已有）     │
        │  · 公钥验签 notify（M7）  │  · RSA-SHA256 真实验签(M7)  │
        │  · 回执字段 out_biz_no   │  · 回执字段 out_bill_no     │
        └──────────┬───────────────┴──────────────┬──────────────┘
                   ▼                              ▼
        ┌──────────────────────┐   ┌──────────────────────┐
        │  POST /payments/     │   │  POST /payments/     │
        │  webhooks/alipay     │   │  webhooks/wechat     │
        │  公钥验签→out_biz_no │   │  RSA验签→out_bill_no │
        │  →mark_executed      │   │  →mark_executed      │
        └──────────────────────┘   └──────────────────────┘

外部 Agent 接入（M7 强化）
  AgentHttpClient（真实 HTTP + Ed25519）
    ├── register / accept_contract / list_my_contracts（已有）
    ├── POST /agent/contracts/{id}/team（M7 新增，组队）
    └── 心跳循环 / 断线重连 / 多客户端并发（M7 脚本+测试）

垂直场景多租户（M7 新增）
  TenantModel（tenant_id, name, scene_config JSON）
    └── outcome_contracts.tenant_id（nullable，兼容存量）
  IpTrialScenario 支持 tenant 维度（模板/档位/角色集按租户配置）
  GET /outcome/tenant-stats（按租户聚合契约数/成交额/完成率）
```

## 4. 分阶段任务（TDD，每步含失败测试→实现→验证→提交）

### 阶段 P1：支付协议完备性补齐（前置基础，无外部依赖）

#### Task P1.1 — `verify_webhook` 协议扩展：携带回执单号

**文件**：
- Modify: `skillos/market/payments/base.py`（协议 + dataclass）
- Modify: `skillos/market/payments/sandbox.py`、`alipay.py`、`wechat.py`
- Modify: `skillos/web_api/payments.py`（webhook 端点取 `receipt.external_ref`）
- Test: `tests/test_payment_webhook.py`

**Step 1: 写失败测试**（`tests/test_payment_webhook.py` 新增）：

```python
class TestWebhookExternalRefMapping:
    def test_alipay_uses_out_biz_no(self, client, db_session):
        cid = _paid_contract(db_session)
        from skillos.market.payouts import PayoutService
        payouts = PayoutService(db_session)
        payouts.generate_for_contract(cid)
        from skillos.db.models import PayoutInstructionModel
        for m in db_session.query(PayoutInstructionModel).filter(PayoutInstructionModel.contract_id == cid):
            m.status = "pending"
            m.external_ref = ""
        db_session.commit()
        ids = [m.id for m in db_session.query(PayoutInstructionModel).filter(PayoutInstructionModel.contract_id == cid)]
        r = client.post(
            "/payments/webhooks/alipay",
            json={
                "app_id": "app-test",
                "notify_type": "fund_trans_order_status",
                "status": "SUCCESS",
                "instruction_ids": ids,
                "out_biz_no": "alipay-real-1",
            },
        )
        # 注意：get_provider("alipay") 无 key 时降级 sandbox，此断言覆盖字段映射逻辑
        assert r.status_code == 200, r.text
        assert all(i["external_ref"] == "alipay-real-1" for i in r.json()["updated"])
```

**Step 2: 运行测试确认失败**：`.venv/bin/pytest tests/test_payment_webhook.py::TestWebhookExternalRefMapping -v` — 期望 FAIL（当前 webhook 取 body 顶层 `external_ref`，非 `out_biz_no`，回写为空）。

**Step 3: 实现**：
- `base.py` 新增 dataclass：

```python
@dataclass
class WebhookReceipt:
    """持牌平台回执验签结果：已确认成功的指令 + 平台侧流水号。"""
    instruction_ids: list[str]
    external_ref: str = ""
```

- 协议 `PaymentProvider.verify_webhook` 返回值改为 `WebhookReceipt`。
- `sandbox.py`：`return WebhookReceipt(instruction_ids=list(instruction_ids), external_ref=body.get("external_ref", ""))`。
- `alipay.py`：`return WebhookReceipt(instruction_ids=list(instruction_ids), external_ref=body.get("out_biz_no", ""))`。
- `wechat.py`：`return WebhookReceipt(instruction_ids=list(instruction_ids), external_ref=resource.get("out_bill_no", ""))`。
- `payments.py` webhook 端点：`receipt = p.verify_webhook(headers, body)`，`external_ref = receipt.external_ref`，遍历 `receipt.instruction_ids`。

**Step 4: 运行测试确认通过**：上述测试 + 既有 `TestWebhook` 全绿。

**Step 5: 提交**：`git add -A && git commit -m "feat: extend verify_webhook to return WebhookReceipt with external_ref"`

#### Task P1.2 — 支付宝公钥 RSA2 验签（可选配置）

**文件**：Modify `alipay.py`；Test `tests/test_payment_adapters.py`

**Step 1: 失败测试**：

```python
class TestAlipayPublicKeyVerification:
    def test_verify_webhook_requires_valid_rsa2_signature_when_pubkey_set(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub_pem = key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode("utf-8")
        provider = AlipayProvider(app_id="app-test", public_key_pem=pub_pem)
        body = {"app_id": "app-test", "notify_type": "fund_trans_order_status", "status": "SUCCESS",
                "instruction_ids": ["pay-1"]}
        with pytest.raises(ValueError, match="signature"):
            provider.verify_webhook({}, body)
```

**Step 3: 实现**：
- `AlipayProvider.__init__` 增加 `public_key_pem: str = ""`，从 `SKILLOS_ALIPAY_PUBLIC_KEY` 读取。
- 新方法 `_verify_rsa2_signature(body)`：从 body 取 `sign`，对其余字段做 `_build_sign_content` 排序拼接 → 用支付宝公钥 `verify(sign, content, PKCS1v15(), SHA256())`。
- `verify_webhook`：若配置了公钥则先验签（失败抛 `ValueError`），再做字段级校验（字段校验逻辑保留，作为无公钥时的降级路径）。

**Step 4/5**: 测试全绿 + 提交。

#### Task P1.3 — 微信 v3 真实 RSA-SHA256 签名（可选配置）

**文件**：Modify `wechat.py`；Test `tests/test_payment_adapters.py`

**Step 1: 失败测试**：

```python
class TestWechatRsaSignature:
    def test_signed_headers_use_rsa_sha256_when_private_key_set(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode("utf-8")
        provider = WeChatPayProvider(mch_id="mch-1", apiv3_key="v3-key",
                                     mch_cert_sn="sn-1", private_key_pem=pem)
        headers = provider._signed_headers("POST", "/v3/x", {"a": 1})
        sig = headers["Authorization"].split('signature="')[1].split('"')[0]
        # 用公钥验签，确认是 RSA 签名而非 HMAC 摘要
        pub = key.public_key()
        content = "POST\n/v3/x\n%s\n%s\n%s\n" % (headers["Authorization"].split('timestamp="')[1].split('"')[0],
                                                 headers["Authorization"].split('nonce_str="')[1].split('"')[0],
                                                 '{"a":1}')
        pub.verify(sig.encode(), content.encode(), padding.PKCS1v15(), hashes.SHA256())
```

**Step 3: 实现**：
- `WeChatPayProvider.__init__` 增加 `private_key_pem: str = ""`，从 `SKILLOS_WECHAT_PRIVATE_KEY` 读取。
- `_signed_headers`：若配置了私钥 → 用 RSA 私钥对 `message` 做 SHA256withRSA，`signature` 为 base64；未配置 → 保留 HMAC-SHA256（沙箱模拟）。

**Step 4/5**: 测试全绿 + 提交。

**P1 验收**：`.venv/bin/ruff check skillos/ scripts/ && .venv/bin/pytest tests/test_payment_webhook.py tests/test_payment_adapters.py tests/test_payment_provider.py -q` 全绿。

### 阶段 P2：真实支付沙箱对接验证（依赖 P1）

#### Task P2.1 — `scripts/verify_payment_sandbox.py`

**文件**：Create `scripts/verify_payment_sandbox.py`

**Step 1: 先写冒烟测试**（`tests/test_payment_sandbox_verify.py`，只测无 key 的 SKIP 分支与加载逻辑）：

```python
def test_no_key_skips(monkeypatch, capfd):
    for k in ("SKILLOS_ALIPAY_APP_ID", "SKILLOS_ALIPAY_PRIVATE_KEY",
              "SKILLOS_WECHAT_MCH_ID", "SKILLOS_WECHAT_APIV3_KEY"):
        monkeypatch.delenv(k, raising=False)
    import importlib.util, sys
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("verify_payment_sandbox",
        Path(__file__).resolve().parent.parent / "scripts" / "verify_payment_sandbox.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rc = mod.main()
    assert rc == 0
    out = capfd.readouterr().out
    assert "SKIP" in out
```

**Step 3: 实现**：脚本遍历 alipay/wechat 两平台：
- 检查必需环境变量；缺失 → 打印 `SKIP: 缺 SKILLOS_*`（rc=0，不失败）。
- 配置完整 → 调 adapter `submit_manifest` 构造载荷 + 打印签名/载荷摘要（**不实际打款**，只验证签名与载荷可构造；真实沙箱打款验证标注为人工执行步骤，需持牌方测试账号）。
- 返回 rc=0（可构造）或 rc=1（构造失败）。

**Step 4/5**: 测试全绿 + 提交。

**P2 验收**：无 key 环境 `SKIP`；有 key 环境可打印签名载荷。

### 阶段 P3：外部 Agent 真实接入内测（独立，可与 P1/P2 并行）

#### Task P3.1 — HTTP 组队端点

**文件**：Modify `skillos/web_api/agent.py`；Modify `scripts/ip_operations_trial.py`（真实模式不再跳过组队）；Test `tests/test_agent_api.py`

**Step 1: 失败测试**：

```python
def test_create_team_via_http(client, agent_identity, cid):
    payload = {"contract_id": cid, "members": [{"member_id": "author-x", "role": "skill_author", "share_ratio": 0.4}]}
    r = client.post("/agent/contracts/%s/team" % cid, json=payload,
                    headers=agent_identity.sign_headers(payload))
    assert r.status_code == 200, r.text
```

**Step 3: 实现**：`agent.py` 新增端点（`_require_agent` 鉴权，contractor 必须等于签名身份）：

```python
@router.post("/contracts/{contract_id}/team")
async def create_team(contract_id: str, payload: dict = Body(...),
                      _agent_id: str = Depends(_require_agent),
                      service: OutcomeContractService = Depends(_get_outcome_service)):
    members = payload.get("members", [])
    try:
        team = service.create_service_team(contract_id, _agent_id, members)
    except ValueError as exc:
        return {"error": str(exc)}
    return {"success": True, "team": team}
```

**Step 4/5**: 测试全绿 + 提交。同步更新 `ip_operations_trial.py` 真实模式用 HTTP 组队替代直连 DB。

#### Task P3.2 — RemoteBridge 心跳过期回收

**文件**：Modify `skillos/protocol/remote_control.py`；Test `tests/test_remote_control.py`（或现有协议测试文件）

**Step 1: 失败测试**：连接后不心跳，`list_bridges` 应过滤过期会话（默认 TTL 如 120s）。

**Step 3: 实现**：`BridgeSession` 增加 `last_seen`；`list_bridges`/`get_stats` 惰性清理 `now - last_seen > TTL` 的会话。

**Step 4/5**: 测试全绿 + 提交。

#### Task P3.3 — 多客户端并发 + 断线重连内测脚本

**文件**：Create `scripts/agent_concurrency_demo.py`；Test `tests/test_agent_http_client.py`（并发冒烟）

**Step 3: 实现**：`threading` 或 `asyncio.gather` 起 N 个 AgentHttpClient（各自 Ed25519 身份）：
- 每个 Agent：注册 → list_open_contracts → accept_contract → 组队 → 心跳 → list_my_contracts。
- 模拟断线：一个客户端 `close()` 后重新 `AgentHttpClient` 同名身份重连（断言 list_my_contracts 仍可查，幂等）。
- 输出各 Agent 结果汇总 + GO/NO-GO。

**Step 4/5**: 冒烟测试 + 提交。

**P3 验收**：`ip_operations_trial.py --real-server` 组队不再跳过；并发内测 GO。

### 阶段 P4：垂直场景多租户上线（最重，schema 变更）

#### Task P4.1 — 数据层：TenantModel + tenant_id

**文件**：Modify `skillos/db/models.py`；Create `migrations/versions/008_add_tenants.py`；Test `tests/test_tenant.py`

**Step 1: 失败测试**（建租户、契约带 tenant_id）：

```python
def test_create_tenant_and_contract(db_session):
    from skillos.market.tenants import TenantService
    svc = TenantService(db_session)
    tenant = svc.create("tenant-ops", "内容代运营事业部", scene_config={"template": "内容代运营"})
    assert tenant.tenant_id == "tenant-ops"
```

**Step 3: 实现**：
- `models.py` 新增 `TenantModel`（`tenants` 表：`tenant_id` PK, `name`, `scene_config` JSON, `created_at/updated_at`）。
- `OutcomeContractModel` 增加 `tenant_id: String(128), nullable, index`。
- 新服务 `skillos/market/tenants.py`：`TenantService.create/get/list/update_scene_config`；`OutcomeContractService.create` 增加可选 `tenant_id` 参数并落库。
- migration `008_add_tenants.py`：幂等 + server_default，`down=007`。

**Step 4/5**: 测试全绿 + 提交。

#### Task P4.2 — 场景包按租户配置

**文件**：Modify `skillos/scenarios/ip_operations.py`；Test `tests/test_ip_operations_scenario.py`

**Step 3: 实现**：`IpTrialScenario.build` 支持 `tenant` 维度 —— 传入 tenant_id 时从 `TenantService.get_scene_config` 读取模板/档位/小费/角色集覆盖默认值；无租户配置则用默认模板。

#### Task P4.3 — 运营看板：按租户聚合

**文件**：Modify `skillos/web_api/outcome.py`；Test `tests/test_outcome_api.py`

**Step 3: 实现**：`GET /outcome/tenant-stats`：按 `tenant_id` 分组聚合 —— 契约数、成交额（price 求和）、完成率（paid/(paid+cancelled)）、平均交付周期。tenant 为空时归入 `"default"`。

**Step 4/5**: 测试全绿 + 提交。

#### Task P4.4 — 多租户并发内测

**文件**：Create `scripts/multi_tenant_trial.py`；Modify `scripts/ip_operations_trial.py`（支持 `--tenant`）；Test `tests/test_multi_tenant_trial.py`（冒烟）

**Step 3: 实现**：脚本循环多个租户各跑一次 `IpTrialScenario` 内测流程（复用 ip_operations_trial 核心），断言各租户契约/出款互相隔离（按 tenant_id 过滤查询）。输出各租户 GO/NO-GO 汇总表。

**P4 验收**：`make audit` 全绿；多租户内测各租户数据隔离。

## 5. 数据层变更汇总

| 变更 | 表 | 内容 | 迁移 |
|------|-----|------|------|
| 新增 | `tenants` | TenantModel（tenant_id/name/scene_config/时间戳） | 008 |
| 修改 | `outcome_contracts` | + `tenant_id`（nullable, index） | 008 |
| 修改 | `payout_instructions.external_ref` | 现有字段，值改为真实平台流水号 | 无 |

## 6. API 一览（M7 新增/修改）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/agent/contracts/{id}/team` | 外部 Agent（contractor）HTTP 组队（P3） |
| POST | `/payments/webhooks/{provider}` | 修改：回执单号改用 `receipt.external_ref`（P1） |
| GET | `/outcome/tenant-stats` | 按租户聚合运营看板（P4） |
| CLI | `scripts/verify_payment_sandbox.py` | 真实沙箱对接验证（有 key 验证/SKIP）（P2） |
| CLI | `scripts/agent_concurrency_demo.py` | 多 Agent 并发 + 断线重连内测（P3） |
| CLI | `scripts/multi_tenant_trial.py` | 多租户并发内测（P4） |

## 7. 测试计划

- `tests/test_payment_webhook.py`：回执单号映射（out_biz_no / out_bill_no / external_ref 三平台）
- `tests/test_payment_adapters.py`：支付宝公钥验签、微信 RSA 真实签名（失败+成功分支）
- `tests/test_payment_sandbox_verify.py`：验证脚本无 key SKIP / 有 key 载荷构造
- `tests/test_agent_api.py`：HTTP 组队端点鉴权 + 权限隔离（非 contractor 403）
- `tests/test_remote_control.py`：心跳过期回收
- `tests/test_agent_http_client.py`：多客户端并发冒烟
- `tests/test_tenant.py`：TenantService + 契约 tenant_id 落库
- `tests/test_ip_operations_scenario.py`：租户场景配置覆盖
- `tests/test_outcome_api.py`：tenant-stats 聚合
- `tests/test_multi_tenant_trial.py`：多租户隔离冒烟

## 8. 红线确认

1. **不托管真实资金**（§9）：P2 验证脚本只构造签名/载荷、**不打款**；真实打款标注人工步骤，需持牌方测试账号。adapter 密钥仅环境变量。
2. **AI 不独立缔约**（§8.2）：组队端点 `_require_agent` 强制 contractor 为签名身份。
3. **密钥不入库**：支付宝公钥/微信私钥仅从环境变量读取，测试用本地生成临时密钥。
4. **泄密预防**：`verify_payment_sandbox.py` 输出不打印密钥本体，只打印签名/载荷摘要。

## 9. 里程碑

| 里程碑 | 内容 | 验收 |
|--------|------|------|
| M7-P1 | 支付协议完备（WebhookReceipt + 公钥验签 + RSA 签名） | 相关测试全绿，ruff 0 问题 |
| M7-P2 | 真实沙箱对接验证脚本（有 key 验证/SKIP） | 无 key 环境 SKIP，rc=0 |
| M7-P3 | 外部 Agent 真实接入（HTTP 组队 + 心跳回收 + 并发重连） | `--real-server` 组队不跳过，并发 GO |
| M7-P4 | 垂直场景多租户（TenantModel + 场景配置 + 看板 + 并发内测） | 租户隔离，`make audit` 全绿 |

## 10. 执行建议

- 新会话用 `superpowers:executing-plans` 逐 Task 执行（每 Task 独立提交）。
- 每个 Task 严格 TDD：先写失败测试 → 实现 → 验证 → 提交。
- P1 必须最先完成（P2 依赖）；P3、P4 与 P1/P2 无依赖可并行。
- 全量验证命令：`.venv/bin/ruff check skillos/ scripts/ && .venv/bin/pytest tests/ --ignore=tests/test_e2e.py --ignore=tests/test_integration.py -q`（e2e/integration 挂起已知）；最终 `make audit`。
- 磁盘旧库（`skillos.db`）schema 不含新列时需删除重建（`create_all` 不加列）。

## 11. 落地记录

### M7 全阶段落地（2026-08-01，Session 8）

**P1 支付协议完备性**（3 提交）：
- P1.1：`verify_webhook` 协议返回 `WebhookReceipt(instruction_ids, external_ref)`（base.py），sandbox 读 `external_ref`、alipay 读 `out_biz_no`、wechat 读 `out_bill_no`；`web_api/payments.py` 用 `receipt.external_ref` 回写。
- P1.2：`AlipayProvider` 可选 `public_key_pem`/`SKILLOS_ALIPAY_PUBLIC_KEY`，配置后 RSA2 验签（PKCS1v15+SHA256），失败抛 `ValueError`；未配置降级字段校验。
- P1.3：`WeChatPayProvider` 可选 `private_key_pem`/`SKILLOS_WECHAT_PRIVATE_KEY`，配置后 `_rsa_sign`（RSA-SHA256，scheme `WECHATPAY2-SHA256-RSA2048`）；未配置保留 HMAC。
- 踩坑：无 key 时工厂降级 sandbox 会因缺 `X-Sandbox-Token` 401，且 sandbox 不读 `out_biz_no`/`out_bill_no` → HTTP 测试需 monkeypatch dummy key 走真实 adapter；RSA 测试需真实密钥（dummy PEM 报 MalformedFraming）。

**P2 真实支付沙箱验证**（1 提交）：`scripts/verify_payment_sandbox.py` 无 key 环境 SKIP（rc=0），有 key 环境构造 alipay/wechat 签名载荷摘要且不打印密钥本体；`tests/test_payment_sandbox_verify.py` 2 用例。

**P3 外部 Agent 真实接入内测**（4 提交）：
- P3.1：`POST /agent/contracts/{id}/team`（`_require_agent` 签名鉴权 + contractor 强制签名身份），`ip_operations_trial.py` 真实模式改走 HTTP 组队（不再跳过）。
- P3.2：`RemoteBridge` 惰性清理心跳超 TTL（默认 120s）的会话，`list_bridges`/`get_stats` 均回收。
- P3.3：`scripts/agent_concurrency_demo.py` N Agent 并发（注册→承接→组队→心跳→断线重连幂等），内置 ASGI + 真实 HTTP 双模式。
- 踩坑：端口 8080 被 openclaw llm_proxy 占用 → 用 9090 验证；2 Agent 竞争同一契约致第二个 accept 失败 → 每 Agent 各建契约；断线重连须复用同一 signer（重建 keypair 签名与注册公钥不符 403）；`_run_single` 曾关闭共享 client 致并发竞态 → 改为每 Agent 独立 AsyncClient，内存 StaticPool 下测试用 `serial=True` 保稳定。

**P4 垂直场景多租户上线**（4 提交）：
- P4.1：`TenantModel`（tenants 表）+ `OutcomeContractModel.tenant_id`（nullable+index）+ `TenantService`（create/get/list/update_scene_config/get_scene_config）+ migration 008（幂等，down=007）。
- P4.2：`IpTrialScenario.build(tenant_id=...)` 从 `TenantService.get_scene_config` 读取模板/档位/小费/角色集覆盖默认；显式参数优先，未知租户降级默认。
- P4.3：`GET /outcome/tenant-stats` 按 tenant_id 聚合（契约数/成交额/完成率/平均交付周期），空租户归 `"default"`。
- P4.4：`scripts/multi_tenant_trial.py` 多租户并发内测（复用 `run_scenario` 核心 + 隔离断言按 tenant_id 过滤），`ip_operations_trial.py --tenant` 支持。

**最终审计**：`make audit` 全绿 — **1431 passed, 0 failed**, 1 skipped，coverage 89.54%（≥80%），ruff + bandit 0 问题，3 verify scripts PASS，pip-audit 0 vulns（2 ignored）。

**下一步候选（M8）**：租户开通 API 化（`POST /tenants` 注册 → 签约方自助开通场景）；tenant-stats 接入运营面板；支付宝/微信真实沙箱账号对接（需持牌方测试 key）；多租户配额/计费隔离。

## 12. 新会话交接指引（执行前必读）

> 直接粘贴到新会话的首条指令即可启动执行。

**启动指令**：

```
用 executing-plans 技能执行 docs/plans/2026-08-01-outcome-contract-m7-design.md。
工作目录为本仓库根目录（SkillOS 开发源），分支 main（有大量未提交的预存改动，不要动它们）。
环境：uv run 不可用，一律 .venv/bin/pytest / .venv/bin/ruff。
全量测试须 --ignore=tests/test_e2e.py --ignore=tests/test_integration.py（这两个挂起）。
P1 必须最先做（P2 依赖）；P3、P4 与 P1/P2 无依赖，可并行。
每 Task 严格 TDD（失败测试→实现→验证→独立提交）。
磁盘旧库 skillos.db 含旧 schema 时会报 no column named base_price，需删除重建。
```

**执行顺序与检查点**：

| 批次 | 任务 | 检查点 |
|------|------|--------|
| 批 1 | P1.1 → P1.2 → P1.3 | 汇报：3 个 Task 实现 + 验证输出 |
| 批 2 | P2 + P3（可并行） | 汇报：验证脚本 SKIP + 并发内测结果 |
| 批 3 | P4.1 → P4.2 → P4.3 → P4.4 | 汇报：租户隔离测试 + 看板聚合 |
| 收尾 | `make audit` 全绿 | 汇报：最终审计数据 + 补 §11 落地记录 |

**关键约束**：

1. **工作区**：`main` 分支有大量未提交的历史改动（M6 及更早的文档/工作流/迁移等），属预存状态，**不属于本任务范围，不得提交或回滚**。本计划产生的改动按 Task 独立 `git add -A && git commit`。
2. **环境**：`.venv/bin/pytest` / `.venv/bin/ruff`（`uv run` 不可用）；全量测试 `--ignore=tests/test_e2e.py --ignore=tests/test_integration.py`（这两个挂起超时，已知）。
3. **磁盘 DB**：默认 `sqlite:///./skillos.db` 旧 schema 会导致 `create_all` 不加新列 → `table outcome_contracts has no column named base_price`；起真实服务/跑脚本前删旧库重建。
4. **无 key 降级**：支付宝公钥/微信 RSA 私钥均为可选配置，未配置时自动降级（公钥验签→字段校验、RSA→HMAC），**保证无 key 全链路可测**；降级路径是设计行为，不是缺陷。
5. **红线**：P2 验证脚本只构造签名/载荷、**不打款**；真实打款标注人工步骤（需持牌方测试账号）。组队端点 `_require_agent` 强制 contractor 为签名身份。脚本输出不打印密钥本体。
6. **验收**：`make audit` 全绿（期望 1350+ passed、coverage ≥80%、ruff 0 问题、3 verify scripts PASS），并补全 §11 落地记录（含踩坑与下一步候选 M8）。
