---
schema_version: "1.0"
type: source_module
purpose: "FastAPI web API — monitoring, security, and health endpoints"
files:
  - "monitoring.py: GET /monitoring/overview, /monitoring/slo, /monitoring/metrics"
  - "security.py: Security audit endpoints, audit log queries"
freshness:
  updated: "2026-07-04"
  version: "0.5.0-beta"
entry_point: "monitoring.py"
agent_instruction: |
  Web API endpoints for monitoring and security.
  - Mounted in app.py via APIRouter
  - Monitoring: SLO summary, metrics snapshot, overview
  - Security: Audit log query and verification
  If a task involves "API endpoints beyond /health and /metrics", start here.
tags: [skillos, api, monitoring, security, fastapi]
cross_reference:
  - "skillos/app.py (main FastAPI app, RED middleware, /health, /metrics)"
  - "skillos/observability/ (metrics backend consumed by these endpoints)"
---

# web_api/

FastAPI monitoring and security endpoints.
