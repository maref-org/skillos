# Contributing to SkillOS

Thank you for contributing to the Skill Operating System.

## Development Setup

```bash
git clone https://github.com/maref-org/skillos.git
cd skillos
uv sync --extra dev
```

## Code Style

- **ruff**: `ruff check skillos/ scripts/ tests/` — 0 violations required
- **mypy**: `mypy skillos/` — strict type checking
- **Python**: 3.11+ 
- **No docstring convention** (keep it minimal)

## Testing

```bash
# Full test suite
uv run pytest tests/ -v --cov

# Core module tests
uv run pytest tests/test_entry_kernel.py tests/test_distribution_engine.py -v

# New features require >= 80% coverage
uv run pytest tests/ -v --cov --cov-report=term --cov-fail-under=80
```

## Pull Request Process

1. Create a feature branch from `main`
2. Write tests for your changes
3. Run `ruff check skillos/ scripts/` and `mypy skillos/` — both must be clean
4. Run `make test` — all tests must pass (see Makefile for ignored hanging test files)
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
- [ ] ruff clean (`ruff check skillos/ scripts/`)
- [ ] mypy clean (`mypy skillos/`)
- [ ] Tests pass (`uv run pytest tests/ -v --cov`)
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
