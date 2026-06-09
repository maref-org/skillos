#!/usr/bin/env python3
"""SkillOS 统一错误码体系

职责：
  - 定义全系统统一的错误码
  - 提供标准化的错误响应格式
  - 支持错误码与 HTTP 状态码映射
  - 支持错误码国际化（预留）

错误码格式：CATEGORY-SUBCATEGORY-SEQUENCE
  - CATEGORY: 2 位字母（如 SE=Security, VA=Validation）
  - SUBCATEGORY: 2 位数字
  - SEQUENCE: 3 位数字
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorCategory(StrEnum):
    """错误类别"""

    SECURITY = "SE"  # 安全类错误
    VALIDATION = "VA"  # 参数校验错误
    AUTHENTICATION = "AU"  # 认证错误
    AUTHORIZATION = "AZ"  # 授权错误
    NOT_FOUND = "NF"  # 资源不存在
    CONFLICT = "CF"  # 资源冲突
    RATE_LIMIT = "RL"  # 限流错误
    EXTERNAL = "EX"  # 外部服务错误
    INTERNAL = "IN"  # 内部错误
    CONFIG = "CO"  # 配置错误


@dataclass
class SkillOSError(Exception):
    """SkillOS 标准错误"""

    code: str
    message: str
    status_code: int = 500
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details or {},
            }
        }


# === 安全类错误 (SE) ===
class SecurityError(SkillOSError):
    """安全类错误基类"""

    def __init__(self, message: str, code: str = "SE-00-001", details: dict[str, Any] | None = None):
        super().__init__(code=code, message=message, status_code=403, details=details)


class HTTPSRequiredError(SecurityError):
    """强制 HTTPS 错误"""

    def __init__(self, details: dict[str, Any] | None = None):
        super().__init__(
            message="HTTPS is required in production. Set SKILLOS_INSECURE=1 for development only.",
            code="SE-01-001",
            details=details,
        )


class InvalidSignatureError(SecurityError):
    """签名验证失败"""

    def __init__(self, details: dict[str, Any] | None = None):
        super().__init__(
            message="Invalid cryptographic signature",
            code="SE-02-001",
            details=details,
        )


class AuditTamperError(SecurityError):
    """审计日志篡改检测"""

    def __init__(self, details: dict[str, Any] | None = None):
        super().__init__(
            message="Audit log tampering detected",
            code="SE-03-001",
            details=details,
        )


# === 参数校验类错误 (VA) ===
class ValidationError(SkillOSError):
    """参数校验错误基类"""

    def __init__(self, message: str, code: str = "VA-00-001", details: dict[str, Any] | None = None):
        super().__init__(code=code, message=message, status_code=400, details=details)


class EmptyFieldError(ValidationError):
    """字段为空"""

    def __init__(self, field: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=f"Field '{field}' cannot be empty",
            code="VA-01-001",
            details={"field": field, **(details or {})},
        )


class InvalidFormatError(ValidationError):
    """格式无效"""

    def __init__(self, field: str, expected: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=f"Field '{field}' has invalid format, expected: {expected}",
            code="VA-02-001",
            details={"field": field, "expected": expected, **(details or {})},
        )


class OutOfRangeError(ValidationError):
    """超出范围"""

    def __init__(self, field: str, min_val: float, max_val: float, details: dict[str, Any] | None = None):
        super().__init__(
            message=f"Field '{field}' must be between {min_val} and {max_val}",
            code="VA-03-001",
            details={"field": field, "min": min_val, "max": max_val, **(details or {})},
        )


# === 认证类错误 (AU) ===
class AuthenticationError(SkillOSError):
    """认证错误基类"""

    def __init__(self, message: str, code: str = "AU-00-001", details: dict[str, Any] | None = None):
        super().__init__(code=code, message=message, status_code=401, details=details)


class InvalidCredentialsError(AuthenticationError):
    """凭据无效"""

    def __init__(self, details: dict[str, Any] | None = None):
        super().__init__(
            message="Invalid credentials",
            code="AU-01-001",
            details=details,
        )


class ChallengeExpiredError(AuthenticationError):
    """挑战已过期"""

    def __init__(self, details: dict[str, Any] | None = None):
        super().__init__(
            message="Challenge has expired",
            code="AU-02-001",
            details=details,
        )


# === 授权类错误 (AZ) ===
class AuthorizationError(SkillOSError):
    """授权错误基类"""

    def __init__(self, message: str, code: str = "AZ-00-001", details: dict[str, Any] | None = None):
        super().__init__(code=code, message=message, status_code=403, details=details)


class PermissionDeniedError(AuthorizationError):
    """权限不足"""

    def __init__(self, resource: str, action: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=f"Permission denied: cannot {action} on {resource}",
            code="AZ-01-001",
            details={"resource": resource, "action": action, **(details or {})},
        )


# === 资源不存在类错误 (NF) ===
class NotFoundError(SkillOSError):
    """资源不存在基类"""

    def __init__(self, resource: str, identifier: str, code: str = "NF-00-001", details: dict[str, Any] | None = None):
        super().__init__(
            code=code,
            message=f"{resource} not found: {identifier}",
            status_code=404,
            details={"resource": resource, "identifier": identifier, **(details or {})},
        )


class IdentityNotFoundError(NotFoundError):
    """身份不存在"""

    def __init__(self, identity_id: str, details: dict[str, Any] | None = None):
        super().__init__(
            resource="Identity",
            identifier=identity_id,
            code="NF-01-001",
            details=details,
        )


class SkillNotFoundError(NotFoundError):
    """Skill 不存在"""

    def __init__(self, skill_id: str, details: dict[str, Any] | None = None):
        super().__init__(
            resource="Skill",
            identifier=skill_id,
            code="NF-02-001",
            details=details,
        )


# === 资源冲突类错误 (CF) ===
class ConflictError(SkillOSError):
    """资源冲突基类"""

    def __init__(self, message: str, code: str = "CF-00-001", details: dict[str, Any] | None = None):
        super().__init__(code=code, message=message, status_code=409, details=details)


class IdentityExistsError(ConflictError):
    """身份已存在"""

    def __init__(self, identity_id: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=f"Identity already exists: {identity_id}",
            code="CF-01-001",
            details={"identity_id": identity_id, **(details or {})},
        )


# === 限流类错误 (RL) ===
class RateLimitError(SkillOSError):
    """限流错误"""

    def __init__(self, retry_after: int = 60, details: dict[str, Any] | None = None):
        super().__init__(
            code="RL-01-001",
            message=f"Rate limit exceeded, retry after {retry_after} seconds",
            status_code=429,
            details={"retry_after": retry_after, **(details or {})},
        )


# === 外部服务类错误 (EX) ===
class ExternalServiceError(SkillOSError):
    """外部服务错误基类"""

    def __init__(self, service: str, message: str, code: str = "EX-00-001", details: dict[str, Any] | None = None):
        super().__init__(
            code=code,
            message=f"External service '{service}' error: {message}",
            status_code=502,
            details={"service": service, **(details or {})},
        )


class CircuitBreakerOpenError(ExternalServiceError):
    """熔断器打开"""

    def __init__(self, service: str, details: dict[str, Any] | None = None):
        super().__init__(
            service=service,
            message="Circuit breaker is open",
            code="EX-01-001",
            details=details,
        )


class RetryExhaustedError(ExternalServiceError):
    """重试耗尽"""

    def __init__(self, service: str, attempts: int, details: dict[str, Any] | None = None):
        super().__init__(
            service=service,
            message=f"All {attempts} retry attempts exhausted",
            code="EX-02-001",
            details={"attempts": attempts, **(details or {})},
        )


# === 内部错误 (IN) ===
class InternalError(SkillOSError):
    """内部错误"""

    def __init__(
        self, message: str = "Internal server error", code: str = "IN-01-001", details: dict[str, Any] | None = None
    ):
        super().__init__(code=code, message=message, status_code=500, details=details)


# === 配置错误 (CO) ===
class ConfigError(SkillOSError):
    """配置错误"""

    def __init__(self, message: str, code: str = "CO-01-001", details: dict[str, Any] | None = None):
        super().__init__(code=code, message=message, status_code=500, details=details)
