# 结构化日志格式规范

**模块**: `kernel/logging_config.py`
**格式**: JSON (每行一个日志条目)

---

## 日志字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `ts` | string | ✅ | ISO 8601 时间戳 (`2026-06-06T10:30:00.123Z`) |
| `level` | string | ✅ | 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL) |
| `logger` | string | ✅ | Logger 名称 (模块路径) |
| `module` | string | ✅ | 模块文件名 |
| `function` | string | ✅ | 函数名 |
| `line` | int | ✅ | 代码行号 |
| `trace_id` | string | ✅ | 链路追踪 ID (16 位 hex, 空表示无上下文) |
| `msg` | string | ✅ | 日志消息 |
| `extra` | object | — | 上下文附加字段 (`user`, `request_id`, `protocol` 等) |

## 示例输出

```json
{"ts": "2026-06-06T10:30:00.123Z", "level": "INFO", "logger": "skillos.kernel.entry_kernel", "module": "entry_kernel.py", "function": "route", "line": 113, "trace_id": "a1b2c3d4e5f6a7b8", "msg": "Routing decision: intent=research path=hybrid risk=low", "extra": {"user": "alice"}}
```

## 使用方式

```python
from skillos.kernel.logging_config import setup_logging, get_logger, TraceContext

# 应用启动时调用一次
setup_logging(level=logging.INFO)

# 模块级 logger
logger = get_logger(__name__)

# 带 trace_id 的日志
with TraceContext(trace_id="abc123", user="alice"):
    logger.info("processing request")
    # 此范围内的所有日志自动携带 trace_id 和 extra 字段

# 自动生成 trace_id
with TraceContext() as tid:
    logger.info("auto-generated trace: %s", tid)
```

## 设计原则

1. **每行一个 JSON** — 兼容 ELK/Loki/Splunk 等日志收集系统
2. **trace_id 传播** — 通过 `contextvars.ContextVar` 在线程/协程间自动传递
3. **向后兼容** — 不影响 `logging` 标准库的常规使用
4. **零依赖** — 仅使用 Python 标准库
