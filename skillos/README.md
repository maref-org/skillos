---
schema_version: "1.0"
type: source_root
purpose: "SkillOS kernel — agent skill scheduling and orchestration"
submodules:
  - "kernel/: Skill execution, intent routing, SLO management"
  - "protocol/: Men0 protocol — agent identity, cards, remote control"
  - "security/: Hallucination detection, sandbox, threat intelligence"
  - "sandbox/: WASM process sandbox for skill isolation"
  - "audit.py: Append-only HMAC-signed audit logger"
  - "db/: SQLAlchemy models, engine, session management"
  - "distribution/: 5/25/70 economic distribution engine"
  - "intelligence/: Intent classification, capability scoring"
  - "negmarket/: NegMarket protocol (skill marketplace)"
  - "observability/: Prometheus metrics, RED middleware"
  - "web_api/: FastAPI monitoring endpoints"
  - "app.py: FastAPI application entry point"
  - "scripts/: CLI tools (competitive intel, etc.)"
freshness:
  updated: "2026-07-30"
  version: "0.5.0-beta"
agent_instruction: |
  This is the SkillOS source package. Each submodule has its own README.
  If you need to understand the architecture, start with skillos/app.py (entry point),
  then skillos/kernel/ (core logic), then the specific module for your task.
  Do NOT look in the KB directory (003-open human) for code-level questions —
  the code itself is the source of truth.
tags: [skillos, source, kernel, python]
cross_reference:
  - "public/skillos/README.md (project overview)"
  - "public/skillos/docs/ (documentation)"
---

# skillos/ — SkillOS Kernel

Source package for the Skill Operating System. Each submodule documented independently.
