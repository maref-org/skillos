"""Web API 签名鉴权共享助手 — C1/C2 安全修复（身份-公钥绑定 + 防重放）

所有 web_api 路由的 ``_require_actor`` / ``_require_agent`` 都应收敛到此模块：

  - 解析请求体与签名头
  - 从 DB 取 ``IdentityModel.public_key_pem``（注册公钥）
  - 用**注册公钥**验签（不信任请求头携带的公钥，防止身份冒充）
  - 校验身份已注册

修复依据（安全审查 C1/C2）：
  - C1：签名只验「头公钥能否验签」而从不与注册公钥比对 → 攻击者可伪造
    密钥对并声明任意已注册 ``X-Signer-Id`` 冒充受害者。此处强制用注册公钥。
  - C2：签名内容未含时间戳 → 攻击者可改写 ``X-Signature-Timestamp`` 绕过
    TTL 无限重放。``MessageSigner.sign/verify`` 已将时间戳纳入签名内容。
"""

from __future__ import annotations

import json
from typing import Any, Iterator

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from skillos.db.engine import get_session
from skillos.db.models import IdentityModel
from skillos.security.message_signer import MessageSigner


async def require_actor(
    request: Request,
    db: Session,
) -> str:
    """验证请求签名并返回签名者身份 ID（未通过则 401/403）。

    C1 修复：用注册公钥（``IdentityModel.public_key_pem``）验签，
    保证签名者身份与已注册公钥绑定，杜绝身份冒充。
    """
    payload = await _parse_payload(request)
    headers = {str(k).lower(): v for k, v in request.headers.items()}
    signer_id = headers.get("x-signer-id", "")
    if not signer_id:
        raise HTTPException(status_code=401, detail="missing x-signer-id")

    identity = db.query(IdentityModel).filter(IdentityModel.identity_id == signer_id).first()
    if identity is None:
        raise HTTPException(status_code=403, detail="identity not registered")

    if not MessageSigner.verify(
        payload,
        headers,
        expected_public_key_pem=identity.public_key_pem,
    ):
        raise HTTPException(status_code=401, detail="invalid or missing signature")

    return signer_id


async def optional_actor(
    request: Request,
    db: Session,
) -> str | None:
    """签名可选版本：无签名头时返回 None（匿名只读），有则强制 require_actor。"""
    lowered = {str(k).lower(): v for k, v in request.headers.items()}
    if not lowered.get("x-signature"):
        return None
    return await require_actor(request, db)


async def _parse_payload(request: Request) -> dict[str, Any]:
    """解析请求体为 dict；空体返回 {}；非法 JSON 抛 422（避免 500）。"""
    raw = await request.body()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="invalid JSON body") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="body must be a JSON object")
    return data


# 兼容 FastAPI Depends 的默认值（与既有 _get_session 依赖一致）
def _get_session() -> Iterator[Session]:
    return get_session()
