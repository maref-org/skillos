"""SkillOS Error Code Registry

All error codes used across the system MUST be registered here.
This enables:
  1. Consistent error responses across all modules
  2. Automatic error code documentation generation
  3. CI validation that no unregistered error codes are used in production paths

Error code format: SKILLOS-{category:02d}-{sub:02d}-{seq:03d}
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any


class ErrorCategory(IntEnum):
    SYSTEM = 1
    KERNEL = 2
    PROTOCOL = 3
    ECONOMIC = 4
    NEGMARKET = 5


_registry: dict[str, "ErrorCode"] = {}


class ErrorCode:
    def __init__(
        self,
        category: ErrorCategory,
        sub: int,
        seq: int,
        message: str,
        http_status: int = 500,
    ):
        self.code = f"SKILLOS-{category.value:02d}-{sub:02d}-{seq:03d}"
        self.category = category
        self.sub = sub
        self.seq = seq
        self.message = message
        self.http_status = http_status
        _registry[self.code] = self

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.code,
            "message": self.message,
            "category": self.category.name,
            "http_status": self.http_status,
        }

    def __repr__(self) -> str:
        return f"<ErrorCode {self.code}: {self.message}>"


def register(
    category: ErrorCategory,
    sub: int,
    seq: int,
    message: str,
    http_status: int = 500,
) -> ErrorCode:
    ec = ErrorCode(category, sub, seq, message, http_status)
    return ec


def lookup(code: str) -> ErrorCode | None:
    return _registry.get(code)


def list_codes() -> list[ErrorCode]:
    return sorted(_registry.values(), key=lambda c: c.code)


def get_error_code(category: ErrorCategory, sub: int, seq: int) -> ErrorCode | None:
    code = f"SKILLOS-{category.value:02d}-{sub:02d}-{seq:03d}"
    return _registry.get(code)


# ── L0 System ──────────────────────────────────────────────────────────
E000 = register(ErrorCategory.SYSTEM, 0, 0, "Unknown system error", 500)
E001 = register(ErrorCategory.SYSTEM, 0, 1, "Internal server error", 500)
E002 = register(ErrorCategory.SYSTEM, 0, 2, "Configuration error", 500)
E003 = register(ErrorCategory.SYSTEM, 0, 3, "Resource not found", 404)
E004 = register(ErrorCategory.SYSTEM, 0, 4, "Operation timeout", 504)
E005 = register(ErrorCategory.SYSTEM, 0, 5, "Dependency unavailable", 503)

# ── L1 Kernel: Session ─────────────────────────────────────────────────
S001 = register(ErrorCategory.KERNEL, 1, 1, "Session not found", 404)
S002 = register(ErrorCategory.KERNEL, 1, 2, "Session expired", 401)
S003 = register(ErrorCategory.KERNEL, 1, 3, "Session already completed", 409)
S004 = register(ErrorCategory.KERNEL, 1, 4, "Session limit reached", 429)
S005 = register(ErrorCategory.KERNEL, 1, 5, "Cannot add item to inactive session", 400)
S006 = register(ErrorCategory.KERNEL, 1, 6, "Session item limit reached", 400)

# ── L1 Kernel: Intent & Routing ────────────────────────────────────────
I001 = register(ErrorCategory.KERNEL, 2, 1, "Intent classification failed", 400)
I002 = register(ErrorCategory.KERNEL, 2, 2, "Risk assessment denied", 403)
I003 = register(ErrorCategory.KERNEL, 2, 3, "Human approval pending", 202)
I004 = register(ErrorCategory.KERNEL, 2, 4, "Unsupported intent type", 400)

# ── L1 Kernel: Skill ──────────────────────────────────────────────────
K001 = register(ErrorCategory.KERNEL, 3, 1, "Skill not found in cache", 404)
K002 = register(ErrorCategory.KERNEL, 3, 2, "Skill execution failed", 500)
K003 = register(ErrorCategory.KERNEL, 3, 3, "Invalid skill manifest", 400)
K004 = register(ErrorCategory.KERNEL, 3, 4, "Skill NFT minting failed", 500)

# ── L1 Kernel: Task Scheduler ──────────────────────────────────────────
T001 = register(ErrorCategory.KERNEL, 4, 1, "Invalid cron expression", 400)
T002 = register(ErrorCategory.KERNEL, 4, 2, "Task not found", 404)
T003 = register(ErrorCategory.KERNEL, 4, 3, "Task execution failed", 500)

# ── L1 Kernel: State Persistor ─────────────────────────────────────────
P001 = register(ErrorCategory.KERNEL, 5, 1, "State save failed", 500)
P002 = register(ErrorCategory.KERNEL, 5, 2, "State not found", 404)
P003 = register(ErrorCategory.KERNEL, 5, 3, "State deserialization error", 500)

# ── L1 Kernel: Web Fetch ──────────────────────────────────────────────
W001 = register(ErrorCategory.KERNEL, 6, 1, "Web fetch failed", 502)
W002 = register(ErrorCategory.KERNEL, 6, 2, "Invalid URL format", 400)
W003 = register(ErrorCategory.KERNEL, 6, 3, "Content extraction failed", 502)

# ── L2 Protocol: Registry ──────────────────────────────────────────────
R001 = register(ErrorCategory.PROTOCOL, 1, 1, "Registry connection failed", 503)
R002 = register(ErrorCategory.PROTOCOL, 1, 2, "Skill registration failed", 500)
R003 = register(ErrorCategory.PROTOCOL, 1, 3, "Skill not found in registry", 404)
R004 = register(ErrorCategory.PROTOCOL, 1, 4, "Registry search failed", 500)
R005 = register(ErrorCategory.PROTOCOL, 1, 5, "Skill publish failed", 500)
R006 = register(ErrorCategory.PROTOCOL, 1, 6, "Skill deprecation failed", 500)

# ── L2 Protocol: Settlement ────────────────────────────────────────────
L001 = register(ErrorCategory.PROTOCOL, 2, 1, "Settlement submission failed", 500)
L002 = register(ErrorCategory.PROTOCOL, 2, 2, "Settlement query failed", 500)

# ── L2 Protocol: Identity ──────────────────────────────────────────────
D001 = register(ErrorCategory.PROTOCOL, 3, 1, "Signature verification failed", 401)
D002 = register(ErrorCategory.PROTOCOL, 3, 2, "Identity not found", 404)
D003 = register(ErrorCategory.PROTOCOL, 3, 3, "Key generation failed", 500)

# ── L2 Protocol: Remote Bridge ─────────────────────────────────────────
B001 = register(ErrorCategory.PROTOCOL, 4, 1, "Bridge not found", 404)
B002 = register(ErrorCategory.PROTOCOL, 4, 2, "Bridge connection failed", 502)
B003 = register(ErrorCategory.PROTOCOL, 4, 3, "Unknown remote command", 400)

# ── L2 Protocol: Matcher ───────────────────────────────────────────────
M001 = register(ErrorCategory.PROTOCOL, 5, 1, "Matcher connection failed", 503)
M002 = register(ErrorCategory.PROTOCOL, 5, 2, "Skill matching failed", 500)

# ── L3 Economic: Distribution ─────────────────────────────────────────
C001 = register(ErrorCategory.ECONOMIC, 1, 1, "Distribution calculation error", 500)
C002 = register(ErrorCategory.ECONOMIC, 1, 2, "Invalid contribution weight", 400)
C003 = register(ErrorCategory.ECONOMIC, 1, 3, "Settlement period not found", 404)
C004 = register(ErrorCategory.ECONOMIC, 1, 4, "Contributor not registered", 404)

# ── L5 NegMarket ───────────────────────────────────────────────────────
N001 = register(ErrorCategory.NEGMARKET, 1, 1, "Negative sample not found", 404)
N002 = register(ErrorCategory.NEGMARKET, 1, 2, "Desensitization failed", 500)
N003 = register(ErrorCategory.NEGMARKET, 1, 3, "Anti-pattern generation failed", 500)
N004 = register(ErrorCategory.NEGMARKET, 1, 4, "Sample already exists", 409)
N005 = register(ErrorCategory.NEGMARKET, 1, 5, "Encryption failed", 500)
N006 = register(ErrorCategory.NEGMARKET, 1, 6, "Decryption failed", 500)
