---
name: social-media-crisis-management
description: "社媒舆情监控与危机响应 — 4级分类(INFO/WATCH/WARNING/CRITICAL)、中英文关键词库、自动响应模板、Bark推送+HumanGate升级。Invoke 当需要监控社媒负面舆情、配置危机响应策略、设计自动回复模板。"
version: "1.0.0"
autoApply: false
dependencies: []
platforms:
  - claude
  - opencode
triggers:
  - "舆情监控"
  - "危机公关"
  - "负面评论"
  - "自动回复"
  - "舆情检测"
  - "crisis response"
  - "sentiment monitor"
  - "危机响应"
  - "评论监控"
input_schema:
  type: object
  properties:
    text:
      type: string
      description: "待检测评论文本"
    platform:
      type: string
      description: "来源平台"
    lang:
      type: string
      enum: [zh, en]
sla:
  target_success_rate: 0.90
  max_latency_ms: 2000
changelog:
  - version: "1.0.0"
    date: "2026-05-08"
    changes: "Initial version — 4-level crisis classification + response templates"
---

# Skill: social-media-crisis-management

## Overview

社媒舆情监控与危机响应系统。实时扫描评论/帖子, 基于关键词密度 + 情感评分判定4级威胁级别, 自动匹配响应模板, 对 WARNING 及以上级别触发 Bark 推送 + HumanGate 升级。

代码位置: `agents/crisis_agent/__init__.py`

---

## 四级分类体系

| 级别 | 触发条件 | 响应策略 |
|:---:|---------|---------|
| **INFO** | 无负面关键词 | 忽略 |
| **WATCH** | 1-2 个负面关键词, sentiment ≤0.2 | 每日汇总 |
| **WARNING** | 3+ 关键词 或 severity ≥2, sentiment >0.4 | 模板回复 + Bark通知 (1h内) |
| **CRITICAL** | 5+ 关键词 或 severity ≥3, sentiment >0.7 | 紧急响应 + HumanGate (立即) |

---

## 关键词库

### 中文

```python
NEGATIVE_KEYWORDS = {
    "security": ["漏洞", "攻击", "泄露", "后门", "破解", "黑客"],
    "reputation": ["骗子", "诈骗", "虚假", "垃圾", "没用", "失望"],
    "incident": ["崩溃", "挂了", "无法使用", "宕机", "数据丢失"],
    "legal": ["起诉", "侵权", "抄袭", "违法", "举报", "律师函"],
}
```

### English

```python
NEGATIVE_KEYWORDS_EN = {
    "security": ["vulnerability", "breach", "backdoor", "exploit"],
    "reputation": ["scam", "fake", "useless", "trash", "disappointed"],
    "incident": ["crash", "down", "outage", "data loss", "broken"],
    "legal": ["sue", "copyright", "violation", "illegal"],
}
```

---

## 自动响应模板

### WATCH (关注)
```
zh: 感谢关注！我们正在持续改进中。如有具体建议欢迎提 issue 🙏
en: Thanks for the feedback! We are continuously improving.
```

### WARNING (警告)
```
zh: 我们注意到了您的反馈，团队已经在跟进这个问题。
    如有更多细节请私信/发 issue，我们会优先处理。
en: Thank you for reporting this. Our team is looking into it.
    Please DM or open an issue with more details.
```

### CRITICAL (紧急)
```
zh: 我们正在紧急处理此问题。请关注我们的官方公告获取最新进展。
    如需直接沟通请联系 security@openhuman.ai
en: URGENT: We are actively addressing this issue.
    Please follow our official channels for updates.
    Contact security@openhuman.ai for direct communication.
```

---

## 升级策略

```python
ESCALATION_RULES = {
    AlertLevel.CRITICAL: "立即通知核心团队 (Bark + HumanGate)",
    AlertLevel.WARNING:  "1小时内通知 (Bark)",
    AlertLevel.WATCH:    "每日汇总",
    AlertLevel.INFO:     "不通知",
}
```

### Bark 推送配置

```bash
export BARK_KEY="your_bark_device_key"
# 获取: https://api.day.app
```

### HumanGate 集成

```python
# autoresearch/human_gate/gate.py
from autoresearch.human_gate.gate import escalate_alert
escalate_alert(alert_id, level, platform, content)
```

---

## 使用示例

### 实时监控评论文本

```python
from agents.crisis_agent import CrisisAgent, AlertLevel

agent = CrisisAgent()

# 扫描单条评论
comment = "OpenHuman has a security vulnerability that leaks user data!!"
alert = agent.scan(comment, platform="github")
print(f"Level: {alert.level.name}, Keywords: {alert.matched_keywords}")
# Level: CRITICAL, Keywords: ['security:vulnerability']

# 自动响应
if alert.level >= AlertLevel.WARNING:
    response = agent.handle(alert, lang="zh")
    print(f"Auto-reply: {response}")
    # Auto-reply: 我们正在紧急处理此问题...

# 日报汇总
report = agent.report()
print(report)
# {"total_alerts": 5, "by_level": {"WARNING": 3, "WATCH": 2}, ...}
```

### 过滤掉正常评论

```python
# 正面评论 → INFO 级别, 不触发任何动作
alert = agent.scan("This project is amazing, great work!", "twitter")
assert alert.level == AlertLevel.INFO  # ✓
```

---

## 测试清单

- [ ] 安全漏洞评论 → CRITICAL
- [ ] 服务宕机评论 → WARNING
- [ ] 轻微不满评论 → WATCH
- [ ] 正面评论 → INFO
- [ ] Bark 推送在 WARNING+ 时触发
- [ ] HumanGate 在 CRITICAL 时升级
- [ ] 中英文关键词都生效

## Changelog

See frontmatter.
