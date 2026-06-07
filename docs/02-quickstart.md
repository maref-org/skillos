# 02. SkillOS Quickstart Guide

**5 minutes to your first Skill execution.**

---

## 1. Installation

```bash
pip install skillos
```

Verify installation:

```bash
python -c "from skillos import SkillKernel; print('SkillOS installed')"
```

---

## 2. Quick Tour

### 2.1 Skill Kernel

```python
from skillos import SkillKernel

kernel = SkillKernel()
manifest = kernel.distill("https://github.com/user/my-skill")
nft = kernel.mint_nft(manifest)
chain = kernel.assemble_tools(nft)
result = kernel.execute(nft.id, {"input": "hello"})
```

### 2.2 Distribution Engine

```python
from skillos import DistributionEngine

engine = DistributionEngine()
allocation = engine.allocate(amount=100.0, skill_id="skill-xxx")
print(allocation.breakdown)  # 5/25/70 split
```

### 2.3 Session Manager

```python
from skillos import SessionManager

mgr = SessionManager()
session = mgr.create_session(user_id="user-1")
print(session.id)
```

---

## 3. CLI Commands

```bash
# Health check
curl http://localhost:8080/health

# Version
python -c "from skillos.version import __version__; print(__version__)"
```

---

## 4. Next Steps

- Read the [Architecture Guide](03-architecture.md)
- Explore the [API Documentation](05-api.md)
- Check [Development Setup](04-development.md)
