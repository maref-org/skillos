---
schema_version: "1.0"
type: source_module
purpose: "Observability — Prometheus metrics, RED middleware, metrics collector"
files:
  - "metrics.py: MetricsCollector — counter/histogram/gauge for RED"
  - "monitoring.py: Web API monitoring endpoints (overview, SLO, snapshot)"
freshness:
  updated: "2026-07-04"
  version: "0.5.0-beta"
entry_point: "metrics.py"
agent_instruction: |
  Metrics and monitoring infrastructure.
  - RED middleware in app.py auto-records Rate/Errors/Duration per request
  - MetricsCollector exposes /metrics endpoint (Prometheus scrape)
  - Monitoring endpoints provide SLO summary, error rate, active sessions
  If a task involves "metrics" or "monitoring", start here.
tags: [skillos, observability, metrics, prometheus, monitoring]
cross_reference:
  - "skillos/app.py (RED middleware consumption)"
  - "skillos/kernel/slo.py (SLO definitions consumed by metrics)"
  - "observability/alerts.yml (Alertmanager rules)"
---

# observability/

Prometheus metrics + RED middleware + monitoring API.
