# M8 — 租户开通 API 化 + 运营面板 + 真实沙箱对接 设计文档

> **上位法**：本文件受 [Athena 系统宪法 v1.5](../../CONSTITUTION.md) 和 [SkillOS 治理框架](../../GOVERNANCE.md) 共同约束。冲突时以宪法优先，其次以治理框架为准。
> **泄密预防**：本仓库不得包含 T3/T2 级内容（路径/Key/IP/时间戳/依赖图）。发布前必须经过叙事转化引擎处理。

## 1. 背景与目标

M7 完成了垂直场景多租户上线的基础层（TenantModel + tenant_id + tenant-stats 聚合端点），但存在三个缺口：

1. **租户无自助开通通道** — 租户目前只能靠脚本/服务层直接建（`TenantService.create`），签约方无法通过 API 自助开通场景。
2. **运营面板仅一个聚合端点** — `GET /outcome/tenant-stats` 只有总量聚合，缺趋势与明细，无法支撑运营看板。
3. **真实沙箱对接无端到端验证路径** — alipay/wechat 沙箱 adapter 已就绪，但 `verify_payment_sandbox.py` 只做签名构造，未对真实沙箱账号做完整提交/查询/回执闭环。

**目标**：让租户成为可自助开通的一等公民；运营面板可直接被看板消费；真实沙箱对接有可执行验证路径（无 key 自动 SKIP，不阻断 CI）。

## 2. 现状与差距

| 能力 | 现状（M7） | M8 差距 |
|------|-----------|---------|
| 租户创建 | 仅服务层/脚本 | 无 API、无幂等开通、无合约状态 |
| 场景配置 | 创建时一次性写入 scene_config | 无开通/变更/状态流转 |
| tenant-stats | 单点聚合（契约数/成交额/完成率/周期） | 无时间趋势、无按租户明细列表 |
| 沙箱对接 | adapter 就绪 + 签名构造脚本 | 无真实账号端到端验证、无状态查询闭环 |

## 3. 架构设计

### 3.1 租户开通 API（M8-P1）

新增 `skillos/web_api/tenants.py`（prefix `/tenants`），复用 `TenantService`：

| 端点 | 方法 | 鉴权 | 说明 |
|------|------|------|------|
| `/tenants` | POST | 签名 | 开通租户（幂等：重复返回 200 + 已有租户） |
| `/tenants/{tenant_id}` | GET | 只读 | 租户详情 + 场景配置 |
| `/tenants` | GET | 只读 | 租户列表 |
| `/tenants/{tenant_id}/scene` | PUT | 签名 | 更新场景配置（模板/档位/小费/角色集） |
| `/tenants/{tenant_id}/activate` | POST | 签名 | 开通场景（状态 draft → active） |

- `TenantModel` 增加 `status`（draft/active）+ 时间戳；`TenantService.create` 增加 `status` 参数，新增 `set_status`。
- 契约创建（`OutcomeContractService.create` 与 `POST /outcome/contracts`）对 `tenant_id` 做**存在性校验**：租户不存在或非 active → 拒绝创建（422）。

### 3.2 运营面板增强（M8-P2）

`GET /outcome/tenant-stats` 增加：
- `trend`：按日聚合近 N 天契约数/成交额（看板折线数据）。
- `contracts`：该租户契约明细（id/状态/金额/创建时间，分页）。
- 保持既有 `stats` 聚合结构向后兼容（不破坏 M7 测试）。

### 3.3 真实沙箱对接验证（M8-P3）

`scripts/verify_payment_sandbox.py` 增强为完整闭环：
1. `--provider alipay|wechat|all` 选择目标沙箱。
2. 有真实沙箱 key → 构造载荷 → **实际提交**（`submit_manifest`）→ 查询状态（`query_status`）→ 校验回执字段。
3. 无 key → `SKIP`（rc=0，不阻断 CI）。
4. 密钥只从环境变量读取，脚本不打印密钥本体。

## 4. 分阶段任务（TDD，每步含失败测试→实现→验证→提交）

### 阶段 P1：租户开通 API 化

**Task P1.1 — TenantModel.status + TenantService.set_status**
- 失败测试 `tests/test_tenant.py`：`create(..., status="draft")` + `set_status` 流转。
- 实现：`TenantModel.status`（String, default "draft"）+ `TenantService.set_status`。

**Task P1.2 — web_api/tenants.py + 契约创建校验**
- 失败测试 `tests/test_tenants_api.py`：注册签名者 → 开通租户 → 查询 → 更新场景 → 激活 → 契约带 tenant_id 创建；未激活租户创建契约被拒。
- 实现：`skillos/web_api/tenants.py`（复用 `MessageSigner` 鉴权，参照 outcome.py 的 `_require_actor`）；`OutcomeContractService.create` 校验租户 active。

### 阶段 P2：运营面板增强

**Task P2.1 — tenant-stats 趋势 + 明细**
- 失败测试 `tests/test_outcome_api.py::TestTenantStats`：`trend` 近 N 天折线 + `contracts` 明细。
- 实现：`get_tenant_stats` 返回 `stats`（兼容）+ `trend` + `contracts`（分页）。

### 阶段 P3：真实沙箱对接验证

**Task P3.1 — verify_payment_sandbox.py 闭环**
- 失败测试 `tests/test_payment_sandbox_verify.py`：有 key 时 `submit_manifest`+`query_status` 全链路断言。
- 实现：脚本支持 `--provider` + 提交/查询/回执校验；无 key SKIP。

**M8 验收**：`make audit` 全绿；租户开通 API 冒烟 GO；tenant-stats 含趋势与明细；沙箱验证脚本无 key SKIP、有 key 闭环。

## 5. 数据层变更汇总

| 变更 | 表 | 内容 | 迁移 |
|------|-----|------|------|
| `tenants.status` | tenants | String(16) default "draft" | 009_add_tenant_status |

## 6. API 一览（M8 新增/修改）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/tenants` | 开通租户（幂等） |
| GET | `/tenants` | 租户列表 |
| GET | `/tenants/{tenant_id}` | 租户详情 |
| PUT | `/tenants/{tenant_id}/scene` | 更新场景配置 |
| POST | `/tenants/{tenant_id}/activate` | 开通场景（draft→active） |
| GET | `/outcome/tenant-stats` | 聚合 + 趋势 + 明细（向后兼容） |

## 7. 测试计划

| 文件 | 用例 |
|------|------|
| `tests/test_tenant.py` | + set_status 流转（P1.1） |
| `tests/test_tenants_api.py` | 租户 API 全链路 + 契约租户校验（P1.2，新建） |
| `tests/test_outcome_api.py::TestTenantStats` | + 趋势/明细（P2.1） |
| `tests/test_payment_sandbox_verify.py` | + 闭环（P3.1） |

## 8. 红线确认

- 不托管真实资金：沙箱提交仅为记账指令验证，绝不用测试 key 冒充真实交易。
- 密钥只从环境变量读取，脚本不打印密钥本体。
- 租户 API 与契约创建强制签名鉴权（复用 MessageSigner），禁止匿名开通。

## 9. 里程碑

| 里程碑 | 内容 | 验收 |
|--------|------|------|
| M8-P1 | 租户开通 API 化 | 租户 API 测试全绿 |
| M8-P2 | 运营面板增强 | 趋势 + 明细测试全绿 |
| M8-P3 | 真实沙箱闭环 | 无 key SKIP + 有 key 闭环测试 |

## 10. 执行建议

- P1 必须最先做（P2 依赖租户状态）；P3 与 P1/P2 无依赖可并行。
- 每个 Task 独立 `git add` 只加本任务文件，不触碰预存改动。
- 真实沙箱 key 缺失时保证无 key 全链路可测（SKIP 降级为设计行为）。

## 11. 落地记录

（待 M8 执行完成后补记。）

## 12. 新会话交接指引

**启动指令**：

```
用 executing-plans 技能执行 docs/plans/2026-08-01-outcome-contract-m8-design.md。
工作目录为本仓库根目录（SkillOS 开发源），分支 main（有大量未提交的预存改动，不要动它们）。
环境：uv run 不可用，一律 .venv/bin/pytest / .venv/bin/ruff。
全量测试须 --ignore=tests/test_e2e.py --ignore=tests/test_integration.py（这两个挂起）。
P1 必须最先做；P3 与 P1/P2 无依赖可并行。
每 Task 严格 TDD（失败测试→实现→验证→独立提交）。
磁盘旧库 skillos.db 含旧 schema 时报 no column named base_price，需删除重建。
```

**执行顺序与检查点**：

| 批次 | 任务 | 检查点 |
|------|------|--------|
| 批 1 | P1.1 → P1.2 | 汇报：租户开通 API 冒烟 + 契约校验 |
| 批 2 | P2.1 → P3.1 | 汇报：面板趋势/明细 + 沙箱闭环 SKIP |
| 收尾 | `make audit` 全绿 | 汇报：最终审计数据 + 补 §11 落地记录 |
