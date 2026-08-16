#!/usr/bin/env python3
"""CSWDP — Carbon-Silicon Wisdom Dividend Protocol

碳硅智慧红利协议。为技能贡献者提供:
  - 生存保障金 (survival_fund): 按当地最低工资 + 贡献加成计算月度保障
  - 成本熔断 (cost_circuit): 四档预算熔断保护
  - 质量门禁 (quality_gate): 自动执行静态扫描与测试并评估覆盖率

实现基于 roadmap §5。API 路由见 .api。
"""

from skillos.cswdp.cost_circuit import CostCircuitBreaker
from skillos.cswdp.models import (
    CostCircuitSnapshot,
    QualityCheckResult,
    QualityReport,
    SurvivalFundRecord,
)
from skillos.cswdp.quality_gate import QualityGate
from skillos.cswdp.survival_fund import SurvivalFundCalculator

__all__ = [
    "SurvivalFundRecord",
    "CostCircuitSnapshot",
    "QualityCheckResult",
    "QualityReport",
    "SurvivalFundCalculator",
    "CostCircuitBreaker",
    "QualityGate",
]

__version__ = "0.6.0"
