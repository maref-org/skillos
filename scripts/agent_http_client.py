#!/usr/bin/env python3
"""真实外部 Agent HTTP 客户端 — Ed25519 签名调用 SkillOS 服务

替代 TestClient：通过真实 HTTP + 签名头访问运行中的 SkillOS 服务。

用法（先起服务）::
    .venv/bin/python scripts/run_server.py --port 8080
    .venv/bin/python -c "from scripts.agent_http_client import AgentHttpClient; ..."

外部 Agent 集成示例::

    from agent_http_client import AgentHttpClient

    agent = AgentHttpClient("http://127.0.0.1:8080", identity_id="agent-demo")
    agent.register()                       # 首次注册 Ed25519 身份
    agent.list_open_contracts()
    agent.accept_contract(contract_id)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx


class AgentHttpClient:
    """外部 Agent 的 HTTP 客户端（Ed25519 签名）。"""

    def __init__(self, base_url: str, identity_id: str, signer=None):
        self.base_url = base_url.rstrip("/")
        self.identity_id = identity_id
        self._client = httpx.Client(timeout=30.0)
        # signer: MessageSigner 实例（首次注册后可持久化私钥）
        self.signer = signer
        self._registered = False

    def close(self) -> None:
        self._client.close()

    # ── 身份 ────────────────────────────────────────────────────────────
    def register(self) -> bool:
        """注册 Ed25519 身份（首次调用；携带公钥）。"""
        from skillos.security.message_signer import MessageSigner

        if self.signer is None:
            self.signer = MessageSigner(signer_id=self.identity_id)
        pem = self.signer._public_key_pem
        r = self._client.post(
            f"{self.base_url}/api/v1/onboarding/register",
            json={"identity_id": self.identity_id, "role": "provider", "public_key_pem": pem},
        )
        if r.status_code == 409:
            self._registered = True  # 已注册过
            return True
        if r.status_code != 200:
            raise RuntimeError(f"register failed: {r.status_code} {r.text}")
        self._registered = True
        return True

    # ── 签名请求 ────────────────────────────────────────────────────────
    def _signed_post(self, path: str, payload: dict) -> httpx.Response:
        headers = self.signer.sign_headers_http(payload) if self.signer else {}
        return self._client.post(f"{self.base_url}/api/v1{path}", json=payload, headers=headers)

    def _get(self, path: str) -> httpx.Response:
        return self._client.get(f"{self.base_url}/api/v1{path}")

    # ── 成果契约（外部 Agent 当项目长） ─────────────────────────────────
    def list_open_contracts(self) -> list[dict]:
        r = self._get("/agent/list_open_contracts")
        r.raise_for_status()
        return r.json()["contracts"]

    def accept_contract(self, contract_id: str) -> dict:
        r = self._signed_post("/agent/accept_contract", {"contract_id": contract_id})
        r.raise_for_status()
        return r.json()

    def list_my_contracts(self) -> list[dict]:
        r = self._get("/agent/list_my_contracts")
        r.raise_for_status()
        return r.json()["contracts"]

    def submit_delivery(self, contract_id: str, evidence_text: str) -> dict:
        r = self._signed_post(
            f"/outcome/contracts/{contract_id}/submit-delivery",
            {"evidence_text": evidence_text},
        )
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    # 冒烟自测：连一个运行中的服务，仅打印 provider 状态
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--identity", default="agent-smoke")
    args = parser.parse_args()

    client = AgentHttpClient(args.url, args.identity)
    try:
        r = client._get("/payments/providers")
        r.raise_for_status()
        print("SkillOS reachable. Payment providers:", r.json())
    finally:
        client.close()
