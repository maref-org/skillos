---
schema_version: "1.0"
type: source_module
purpose: "Core kernel — skill execution, intent routing, orchestration, SLO management"
files:
  - "skill_kernel.py: Skill execution engine, tool assembly, MCP protocol"
  - "entry_kernel.py: Intent classification and dispatch"
  - "agent_scheduler.py: Agent scheduling and fallback logic"
  - "slo.py: SLO definitions, error budget burn-rate calculation"
  - "orchestrator.py: Process supervision (cold/warm/hot)"
  - "logging_config.py: Structured logging setup"
  - "feature_flags.py: Feature flag system"
  - "session_manager.py: Session lifecycle management"
freshness:
  updated: "2026-07-04"
  version: "0.5.0-beta"
entry_point: "skill_kernel.py (execution), slo.py (quality)"
agent_instruction: |
  This is the brain of SkillOS.
  - Skill execution: skill_kernel.py (assemble_tools, execute_skill)
  - Intent routing: entry_kernel.py (classify_intent, route)
  - Quality: slo.py (SLOConfig, SLOManager, ErrorBudget)
  - Orchestration: orchestrator.py (spawn, supervise, restart)
  If a task involves "running a skill", start in skill_kernel.py.
  If a task involves "how reliable is it", start in slo.py.
tags: [skillos, kernel, execution, slo, routing]
cross_reference:
  - "skillos/protocol/agent_card.py (agent identity → kernel consumes)"
---

# kernel/

Core SkillOS kernel — execution, routing, SLO management.
