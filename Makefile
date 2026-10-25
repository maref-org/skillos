.PHONY: test lint security audit coverage gate install-hooks start-health-daemon stop-health-daemon meta-audit

IGNORE_HANGING =

test:
	.venv/bin/python -m pytest tests/ -v --tb=short $(IGNORE_HANGING)

coverage:
	.venv/bin/python -m pytest --cov-fail-under=80 --cov=skillos --cov-report=term-missing $(IGNORE_HANGING)

lint:
	.venv/bin/ruff check .

security:
	.venv/bin/bandit -r skillos/ -c pyproject.toml --severity-level medium

audit: gate

# 单一门禁入口：本地与 CI 执行同一脚本
gate:
	bash scripts/release_gate.sh

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
	.venv/bin/python -m pre_commit install --hook-type pre-commit
	.venv/bin/python -m pre_commit install --hook-type pre-push
	@echo "✅ Hooks installed: pre-commit (athena-leak-check) + pre-push (athena-sanitize-push)"
	@echo "   治理红线第 2 条：禁止以 --no-verify 绕过 pre-push hook"
