# Contributing to SkillOS

Thank you for contributing to the Skill Execution Kernel.

## Development Setup

```bash
git clone https://github.com/skillos-team/skillos.git
cd skillos
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Code Style

- **ruff**: `ruff check .` — 0 violations required
- **mypy**: `mypy .` — strict type checking with `disallow_untyped_defs=true`
- **Python**: 3.11+ with `from __future__ import annotations`

## Testing

```bash
# Full test suite
pytest tests/ -v --cov

# Specific test categories
pytest tests/test_skill_kernel.py -v
pytest tests/test_distribution_engine.py -v
pytest tests/test_entry_kernel.py -v
```

## Pull Request Process

1. Create a feature branch from `main`
2. Write tests for your changes
3. Run `ruff check .` and `mypy .` — both must be clean
4. Run `pytest tests/ -v --cov` — all tests must pass
5. Update CHANGELOG.md under the `## Unreleased` section
6. Submit a PR with a descriptive title and body

## PR Template

```markdown
## Summary
Brief description of changes.

## Type
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Performance improvement
- [ ] Security fix

## Verification
- [ ] ruff clean (`ruff check .`)
- [ ] mypy clean (`mypy .`)
- [ ] Tests pass (`pytest tests/ -v --cov`)
- [ ] New tests added for changed functionality
```

## Commit Messages

Follow conventional commits:
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `test:` adding tests
- `refactor:` code restructuring
- `perf:` performance improvement
- `security:` security-related changes

## Code Review

All PRs require at least one approving review before merge. Reviewers check for:
1. Code correctness and safety implications
2. Test coverage and quality
3. Style consistency (ruff + mypy)
4. Documentation completeness
