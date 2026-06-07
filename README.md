# SkillOS — Skill Operating System (v0.4.0-alpha)

**Agent skill scheduling and orchestration kernel.**

SkillOS is the terminal implementation layer of the OpenHuman Protocol — a Python 3.11+ backend for multi-agent skill execution with a built-in 5/25/70 economic model.

## Quick Start

```bash
uv sync --extra dev
uv run pytest
```

## Architecture

```
L3 经济层    5/25/70 分配引擎 · NegMarket 负样本市场 · 生态基金
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
make audit    # full release gate
```

## License

AGPL-3.0 — see [LICENSE](LICENSE).
