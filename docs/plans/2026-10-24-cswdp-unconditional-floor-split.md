# CSWDP 地板/天花板分账：生存保障金拆分设计

> **上位法**: 本计划受 [Athena 系统宪法 v2.2](../../CONSTITUTION.md) 和 [SkillOS 治理框架](../../GOVERNANCE.md) 共同约束。
> **红线**: 不托管真实资金（§9）；不引入 T3/T2 级内容。
> **前置**: v0.6.0-beta 的 `skillos/cswdp/`（单公式版本）已上线。

## 1. 背景

v0.6.0 的生存保障金公式把无条件基础与绩效加成合并为同一个 `total_amount`：

```
基础保障 = 当地月最低工资 × 1.5
贡献加成 = 基础保障 × (历史贡献度×0.4 + 成功率×0.3 + 治理参与×0.3)
总保障金 = min(基础保障 + 贡献加成, 基础保障 × 3.0)
```

问题不在算术，在语义：**地板的一部分挂在了绩效上**。三个后果在规模化后必然出现。

1. **目标人群错位**：最需要地板的人（新人、失败者、低治理参与的老实人）恰好拿最低加成。
2. **指标博弈**：治理参与比做事便宜，刷参与成为理性策略。
3. **合法性流失**：领取额取决于一个本人无法解释的分数，领取从权利退化为恩典。

这与"地板无条件、天花板靠自愿、承重墙不可拆"的分配原则直接冲突，也与本仓库在 `docs/plans/2026-08-01-outcome-contract-design.md` 中确立的四边生态定位冲突。

## 2. 关键决策

### D1 两笔钱、两个账户、两套规则

```
无条件基础 = 当地月最低工资 × 1.5                  → survival 账户（地板）
绩效奖金   = 基础 × (贡献×0.4 + 成功率×0.3 + 治理×0.3)  → ceiling 账户（天花板）
绩效奖金上限 = 基础 × 2.0（合计仍 ≤ 基础 × 3.0）
```

- 地板：不参与任何 clamp / min / 条件分支，零因子时金额不变；不可申诉（人人都有，无需申诉）。
- 奖金：可申诉（有争议，走仲裁）；不得成为生存的唯一来源。

### D2 保持向后兼容的字段

`SurvivalFundRecord` 保留 `base_amount` / `bonus_amount` / `total_amount`，新增：

- `unconditional_amount`：无条件部分（恒等于 `base_amount`）
- `performance_bonus`：绩效奖金（恒等于 `bonus_amount`）
- `accounts`：`{"survival": x, "ceiling": y}`
- `floor_is_unconditional`（property）：地板不变式，供审计与测试断言

旧调用方无需改动；新调用方应读 `accounts` 做分账。

### D3 上限语义

`cap_multiplier=3.0` 表示合计上限，绩效奖金上限 = `base × (cap_multiplier - 1)`。构造时校验 `cap_multiplier >= 1.0`（否则抛 `ValueError`），保证地板永远不会被上限削掉。

### D4 可选关闭奖金

`calculate(..., include_performance_bonus=False)` 只算地板。用途：审计口径、政策演示、地板压力测试。

## 3. 文件变更

| 文件 | 变更 |
|---|---|
| `skillos/cswdp/models.py` | 新增 `unconditional_amount` / `performance_bonus` / `accounts` / `floor_is_unconditional` |
| `skillos/cswdp/survival_fund.py` | 拆分计算；常量 `FLOOR_ACCOUNT` / `CEILING_ACCOUNT`；构造校验；`describe()` 增账户与策略字段 |
| `skillos/cswdp/api.py` | 请求体新增 `include_performance_bonus`（默认 True） |
| `tests/test_cswdp.py` | +8 用例（地板不变式、账户隔离、上限不侵地板、仅地板模式、API） |

## 4. 验收标准

- [x] `pytest tests/test_cswdp.py` 全绿（32 passed）
- [x] 地板不变式：任意因子组合下 `unconditional_amount == base_amount`
- [x] 零贡献者与满贡献者地板完全相同
- [x] 上限生效时只截奖金，不截地板
- [x] `ruff check skillos/cswdp/ tests/test_cswdp.py` 无告警

## 5. 后续

- 账本侧：`payout_instructions` 需要为 `survival` / `ceiling` 两账户分别出款（当前 CSWDP 仅计算，不生成指令）。
- 治理侧：地板金额的锚定值（最低工资倍数）应进入生态基金理事会审议范围，不由平台单方调整。
