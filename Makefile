.PHONY: test lint security audit coverage install-hooks start-health-daemon stop-health-daemon meta-audit

# Phase 0/1: All 1127 tests pass (unit + integration + e2e). No ignores needed.
IGNORE_HANGING =

# Acceptable-risk CVEs (workspace-constrained or low-impact):
#   cryptography  GHSA-537c-gmf6-5ccf — OpenSSL bundling (Ed25519 unaffected)
#   msgpack       GHSA-6v7p-g79w-8964 — workspace-constrained (mitmproxy)
PIP_AUDIT_IGNORE = --ignore-vuln GHSA-537c-gmf6-5ccf --ignore-vuln GHSA-6v7p-g79w-8964

test:
	.venv/bin/python -m pytest tests/ -v --tb=short $(IGNORE_HANGING)

coverage:
	.venv/bin/python -m pytest --cov-fail-under=80 --cov=skillos --cov-report=term-missing $(IGNORE_HANGING)

lint:
	.venv/bin/ruff check skillos/ scripts/

security:
	.venv/bin/bandit -r skillos/ -c pyproject.toml --severity-level medium

audit: lint security coverage
	.venv/bin/python scripts/verify_distribution.py
	.venv/bin/python scripts/arch_check.py
	.venv/bin/python scripts/verify_kb_sync.py
	.venv/bin/pip-audit $(PIP_AUDIT_IGNORE)

start-health-daemon:
	python3 scripts/health_snapshot_daemon.py --daemon

stop-health-daemon:
	python3 scripts/health_snapshot_daemon.py --stop

meta-audit:
	SKILLOS_AUDIT_SECRET="$${SKILLOS_AUDIT_SECRET}" python3 scripts/meta_monitor.py

# Phase B: Production hardening
k6-test:
	k6 run scripts/load-test.js -e BASE_URL="${BASE_URL:-http://localhost:8000}"

docker-build:
	docker build -t skillos:latest .

docker-sbom:
	syft skillos:latest -o spdx-json > sbom.spdx.json

cosign-sign:
	cosign sign --yes ${IMAGE}

semgrep-scan:
	.venv/bin/pip install semgrep && .venv/bin/semgrep --config=.semgrep/rules/ --error --strict skillos/

chaos-test:
	.venv/bin/python scripts/chaos_test.py

install-hooks:
	@echo "📦 Installing pre-commit + pre-push hooks..."
	.venv/bin/pre-commit install --hook-type pre-commit
	.venv/bin/pre-commit install --hook-type pre-push
	@echo "✅ Hooks installed: pre-commit (athena-leak-check) + pre-push (athena-sanitize-push)"
	@echo "   治理红线第 2 条：禁止以 --no-verify 绕过 pre-push hook"
