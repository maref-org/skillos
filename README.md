# SkillOS — Skill Operating System (v0.6.0-beta.2)

**Agent skill scheduling and orchestration kernel.**

SkillOS is the terminal implementation layer of the OpenHuman Protocol — a Python 3.11+ backend for multi-agent skill execution with a built-in 5/25/70 economic model.

## Quick Start

```bash
pip install -e ".[dev,web]"
pytest
```

## Architecture

```
L3 经济层    5/25/70 分配引擎 · Skill Market L3 MVP · NegMarket 负样本市场
             生态基金 · Registry / Pricing / Settlement
L2 协议层    Registry / Matcher / Settlement / Identity / Remote Bridge
L1 内核层    EntryKernel · AgentScheduler · SkillKernel · SessionManager
             SessionIsolator · StatePersistor · TaskScheduler · WebFetcher
L0 基础层    结构化日志 · Prometheus 指标 · OTel 追踪 · 错误码系统
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## Development

```bash
make test     # run all tests
make lint     # ruff check
make gate     # full release gate (same script as CI)
```

## Inspiration

The intelligence layer (`skillos.intelligence`) design was inspired by concurrent academic research on skill self-evolution
(independently implemented, no code or data shared):

- **SkillEvolver: Skill Learning as a Meta-Skill** — Genrui Zhang et al., arXiv:2605.10500, May 2026
- **EmbodiSkill: Skill-Aware Reflection for Self-Evolving Embodied Agents** — Ruofei Ju et al., arXiv:2605.10332, May 2026

SkillOS's evolution loop uses its own Agent execution logs and architecture vocabulary,
not derived from any external codebase.

## License

AGPL-3.0 — see [LICENSE](LICENSE).
