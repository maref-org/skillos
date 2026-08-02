---
schema_version: "1.0"
type: source_module
purpose: "Economic distribution engine — 5/25/70 revenue split model"
files:
  - "engine.py: DistributionEngine — revenue distribution, contributor splits"
  - "repository.py: Distribution data persistence"
freshness:
  updated: "2026-07-04"
  version: "0.5.0-beta"
entry_point: "engine.py"
agent_instruction: |
  Distribution engine implementing the 5/25/70 model:
  - 5% platform fee
  - 25% ecosystem fund
  - 70% contributor pool (split among creator/worker/referrer/platform/community)
  If a task involves "revenue" or "distribution" or "5/25/70", start here.
tags: [skillos, distribution, economics, revenue, 5-25-70]
cross_reference:
  - "scripts/verify_distribution.py (distribution model validation)"
---

# distribution/

5/25/70 economic distribution engine for skill marketplace.
