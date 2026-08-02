# SkillOS 错误码矩阵

**自动生成**: `skillos/kernel/error_codes.py` — 所有错误码在此注册
**格式**: `SKILLOS-{category:02d}-{sub:02d}-{seq:03d}`
**共 55 个错误码，5 个类别**

---

## ErrorCategory.SYSTEM (1)

| 代码 | 常量 | HTTP | 说明 |
|------|------|:----:|------|
| `SKILLOS-01-00-000` | `E000` | 500 | Unknown system error |
| `SKILLOS-01-00-001` | `E001` | 500 | Internal server error |
| `SKILLOS-01-00-002` | `E002` | 500 | Configuration error |
| `SKILLOS-01-00-003` | `E003` | 404 | Resource not found |
| `SKILLOS-01-00-004` | `E004` | 504 | Operation timeout |
| `SKILLOS-01-00-005` | `E005` | 503 | Dependency unavailable |

## ErrorCategory.KERNEL (2)

### Sub 1: Session

| 代码 | 常量 | HTTP | 说明 |
|------|------|:----:|------|
| `SKILLOS-02-01-001` | `S001` | 404 | Session not found |
| `SKILLOS-02-01-002` | `S002` | 401 | Session expired |
| `SKILLOS-02-01-003` | `S003` | 409 | Session already completed |
| `SKILLOS-02-01-004` | `S004` | 429 | Session limit reached |
| `SKILLOS-02-01-005` | `S005` | 400 | Cannot add item to inactive session |
| `SKILLOS-02-01-006` | `S006` | 400 | Session item limit reached |

### Sub 2: Intent & Routing

| 代码 | 常量 | HTTP | 说明 |
|------|------|:----:|------|
| `SKILLOS-02-02-001` | `I001` | 400 | Intent classification failed |
| `SKILLOS-02-02-002` | `I002` | 403 | Risk assessment denied |
| `SKILLOS-02-02-003` | `I003` | 202 | Human approval pending |
| `SKILLOS-02-02-004` | `I004` | 400 | Unsupported intent type |

### Sub 3: Skill

| 代码 | 常量 | HTTP | 说明 |
|------|------|:----:|------|
| `SKILLOS-02-03-001` | `K001` | 404 | Skill not found in cache |
| `SKILLOS-02-03-002` | `K002` | 500 | Skill execution failed |
| `SKILLOS-02-03-003` | `K003` | 400 | Invalid skill manifest |
| `SKILLOS-02-03-004` | `K004` | 500 | Skill NFT minting failed |

### Sub 4: Task Scheduler

| 代码 | 常量 | HTTP | 说明 |
|------|------|:----:|------|
| `SKILLOS-02-04-001` | `T001` | 400 | Invalid cron expression |
| `SKILLOS-02-04-002` | `T002` | 404 | Task not found |
| `SKILLOS-02-04-003` | `T003` | 500 | Task execution failed |

### Sub 5: State Persistor

| 代码 | 常量 | HTTP | 说明 |
|------|------|:----:|------|
| `SKILLOS-02-05-001` | `P001` | 500 | State save failed |
| `SKILLOS-02-05-002` | `P002` | 404 | State not found |
| `SKILLOS-02-05-003` | `P003` | 500 | State deserialization error |

### Sub 6: Web Fetch

| 代码 | 常量 | HTTP | 说明 |
|------|------|:----:|------|
| `SKILLOS-02-06-001` | `W001` | 502 | Web fetch failed |
| `SKILLOS-02-06-002` | `W002` | 400 | Invalid URL format |
| `SKILLOS-02-06-003` | `W003` | 502 | Content extraction failed |

## ErrorCategory.PROTOCOL (3)

### Sub 1: Registry

| 代码 | 常量 | HTTP | 说明 |
|------|------|:----:|------|
| `SKILLOS-03-01-001` | `R001` | 503 | Registry connection failed |
| `SKILLOS-03-01-002` | `R002` | 500 | Skill registration failed |
| `SKILLOS-03-01-003` | `R003` | 404 | Skill not found in registry |
| `SKILLOS-03-01-004` | `R004` | 500 | Registry search failed |
| `SKILLOS-03-01-005` | `R005` | 500 | Skill publish failed |
| `SKILLOS-03-01-006` | `R006` | 500 | Skill deprecation failed |

### Sub 2: Settlement

| 代码 | 常量 | HTTP | 说明 |
|------|------|:----:|------|
| `SKILLOS-03-02-001` | `L001` | 500 | Settlement submission failed |
| `SKILLOS-03-02-002` | `L002` | 500 | Settlement query failed |

### Sub 3: Identity

| 代码 | 常量 | HTTP | 说明 |
|------|------|:----:|------|
| `SKILLOS-03-03-001` | `D001` | 401 | Signature verification failed |
| `SKILLOS-03-03-002` | `D002` | 404 | Identity not found |
| `SKILLOS-03-03-003` | `D003` | 500 | Key generation failed |

### Sub 4: Remote Bridge

| 代码 | 常量 | HTTP | 说明 |
|------|------|:----:|------|
| `SKILLOS-03-04-001` | `B001` | 404 | Bridge not found |
| `SKILLOS-03-04-002` | `B002` | 502 | Bridge connection failed |
| `SKILLOS-03-04-003` | `B003` | 400 | Unknown remote command |

### Sub 5: Matcher

| 代码 | 常量 | HTTP | 说明 |
|------|------|:----:|------|
| `SKILLOS-03-05-001` | `M001` | 503 | Matcher connection failed |
| `SKILLOS-03-05-002` | `M002` | 500 | Skill matching failed |

## ErrorCategory.ECONOMIC (4)

| 代码 | 常量 | HTTP | 说明 |
|------|------|:----:|------|
| `SKILLOS-04-01-001` | `C001` | 500 | Distribution calculation error |
| `SKILLOS-04-01-002` | `C002` | 400 | Invalid contribution weight |
| `SKILLOS-04-01-003` | `C003` | 404 | Settlement period not found |
| `SKILLOS-04-01-004` | `C004` | 404 | Contributor not registered |

## ErrorCategory.NEGMARKET (5)

| 代码 | 常量 | HTTP | 说明 |
|------|------|:----:|------|
| `SKILLOS-05-01-001` | `N001` | 404 | Negative sample not found |
| `SKILLOS-05-01-002` | `N002` | 500 | Desensitization failed |
| `SKILLOS-05-01-003` | `N003` | 500 | Anti-pattern generation failed |
| `SKILLOS-05-01-004` | `N004` | 409 | Sample already exists |
| `SKILLOS-05-01-005` | `N005` | 500 | Encryption failed |
| `SKILLOS-05-01-006` | `N006` | 500 | Decryption failed |

---

**通过条件**: 所有 API 响应中包含 `error_code` 字段且值在本矩阵中可查。
