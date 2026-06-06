.PHONY: test lint security audit

test:
	.venv/bin/python -m pytest tests/ -v --tb=short

lint:
	.venv/bin/ruff check kernel/ protocol/ distribution/ negmarket/ scripts/

security:
	.venv/bin/bandit -r kernel/ protocol/ distribution/ negmarket/

audit: lint security test
	.venv/bin/python scripts/verify_distribution.py
	.venv/bin/python scripts/arch_check.py
	.venv/bin/python scripts/verify_kb_sync.py
