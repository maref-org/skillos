.PHONY: test lint security audit coverage

test:
	.venv/bin/python -m pytest tests/ -v --tb=short

coverage:
	.venv/bin/python -m pytest --cov-fail-under=70 --cov=kernel --cov=distribution --cov=protocol --cov=negmarket --cov-report=term-missing

lint:
	.venv/bin/ruff check kernel/ protocol/ distribution/ negmarket/ scripts/

security:
	.venv/bin/bandit -r kernel/ protocol/ distribution/ negmarket/

audit: lint security coverage
	.venv/bin/python scripts/verify_distribution.py
	.venv/bin/python scripts/arch_check.py
	.venv/bin/python scripts/verify_kb_sync.py
	.venv/bin/pip-audit
