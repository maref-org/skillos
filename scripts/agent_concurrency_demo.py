#!/usr/bin/env python3
"""多 Agent 并发 + 断线重连内测（M7-P3.3）

每个 Agent（独立 Ed25519 身份）：注册 → 浏览 open 契约 → 承接 → 组队 → 心跳
→ 查询我的契约 → 断线重连（close 后同名身份重连，幂等）。

运行::
    # 真实服务模式（先起服务）
    .venv/bin/python scripts/run_server.py --port 8080 &
    .venv/bin/python scripts/agent_concurrency_demo.py --url http://127.0.0.1:8080 --agents 3

    # 内置模式（内存 DB + ASGI transport）
    .venv/bin/python scripts/agent_concurrency_demo.py --agents 3
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class _Agent:
    """单个外部 Agent 的全流程：基于 async HTTP + Ed25519 签名。"""

    def __init__(self, base_url: str, identity_id: str, client, signer=None):
        from skillos.security.message_signer import MessageSigner

        self.base_url = base_url.rstrip("/")
        self.identity_id = identity_id
        self.signer = signer or MessageSigner(signer_id=identity_id)
        self._client = client
        self.contract_id: str | None = None

    async def register(self) -> bool:
        r = await self._client.post(
            f"{self.base_url}/api/v1/onboarding/register",
            json={
                "identity_id": self.identity_id,
                "role": "provider",
                "public_key_pem": self.signer._public_key_pem,
            },
        )
        return r.status_code in (200, 409)

    def _signed_headers(self, payload: dict) -> dict:
        return self.signer.sign_headers_http(payload)

    async def list_open(self) -> list[dict]:
        r = await self._client.get(f"{self.base_url}/api/v1/agent/list_open_contracts")
        r.raise_for_status()
        return r.json()["contracts"]

    async def accept(self, contract_id: str) -> bool:
        payload = {"contract_id": contract_id}
        r = await self._client.post(
            f"{self.base_url}/api/v1/agent/accept_contract",
            json=payload,
            headers=self._signed_headers(payload),
        )
        return r.status_code == 200

    async def create_team(self, contract_id: str) -> bool:
        payload = {
            "contract_id": contract_id,
            "members": [{"member_id": f"author-{self.identity_id}", "share_ratio": 0.4}],
        }
        r = await self._client.post(
            f"{self.base_url}/api/v1/agent/contracts/{contract_id}/team",
            json=payload,
            headers=self._signed_headers(payload),
        )
        return r.status_code == 200 and r.json().get("success", False)

    async def heartbeat(self, session_id: str) -> bool:
        payload = {"session_id": session_id}
        r = await self._client.post(
            f"{self.base_url}/api/v1/agent/bridges/heartbeat",
            json=payload,
            headers=self._signed_headers(payload),
        )
        return r.status_code == 200 and r.json().get("success", False)

    async def connect_bridge(self, session_id: str) -> bool:
        payload = {"session_id": session_id, "remote_url": "https://peer.example.com", "api_key": "k"}
        r = await self._client.post(
            f"{self.base_url}/api/v1/agent/bridges/connect",
            json=payload,
            headers=self._signed_headers(payload),
        )
        return r.status_code == 200 and r.json().get("success", False)

    async def list_my(self) -> list[dict]:
        r = await self._client.get(
            f"{self.base_url}/api/v1/agent/list_my_contracts",
            headers=self._signed_headers({}),
        )
        r.raise_for_status()
        return r.json()["contracts"]


async def _run_single(base_url: str, identity_id: str, transport=None, contract_id: str | None = None) -> dict:
    """单个 Agent 的完整生命周期（含断线重连幂等验证）。

    每个 Agent 使用独立 AsyncClient（并发/串行均安全），断线重连时
    关闭自身 client 并重建，复用同一 signer（同名身份幂等）。
    """
    from httpx import AsyncClient

    client = AsyncClient(base_url=base_url, timeout=30.0, transport=transport)
    agent = _Agent(base_url, identity_id, client)
    try:
        await agent.register()

        open_contracts = await agent.list_open()
        my_cid = contract_id or (open_contracts[0]["id"] if open_contracts else None)
        if not my_cid:
            return {"identity": identity_id, "ok": False, "reason": "no open contracts"}

        accepted = await agent.accept(my_cid)
        teamed = await agent.create_team(my_cid)
        connected = await agent.connect_bridge(f"bridge-{identity_id}")
        heartbeat = await agent.heartbeat(f"bridge-{identity_id}")
        mine = await agent.list_my()

        # 断线重连：close 后重建 client，但复用同一 signer（同名身份幂等）
        await client.aclose()
        new_client = AsyncClient(base_url=base_url, timeout=30.0, transport=transport)
        try:
            agent2 = _Agent(base_url, identity_id, new_client, signer=agent.signer)
            await agent2.register()
            mine_after = await agent2.list_my()
        finally:
            await new_client.aclose()

        ok = (
            accepted
            and teamed
            and connected
            and heartbeat
            and any(c["id"] == my_cid for c in mine)
            and any(c["id"] == my_cid for c in mine_after)
        )
        return {"identity": identity_id, "contract_id": my_cid, "ok": ok}
    finally:
        try:
            await client.aclose()
        except Exception:
            pass


async def run_demo(
    base_url: str,
    n_agents: int,
    contract_ids: list[str] | None = None,
    transport=None,
    serial: bool = False,
) -> list[dict]:
    """并发运行 N 个 Agent，返回各自的 GO/NO-GO 结果。

    contract_ids: 每个 Agent 独立的承接目标（并发下避免竞争同一契约）；
                  None 时各 Agent 取当前第一个 open 契约。
    transport: 可选的 httpx transport（测试注入 ASGITransport 以等价真实 HTTP）。
    serial: True 时顺序执行（内存 SQLite StaticPool 单连接不支持并发写，
            测试环境需串行以保证稳定；真实服务模式保持并发默认 False）。
    """
    coros = [
        _run_single(
            base_url,
            f"agent-conc-{i}",
            transport=transport,
            contract_id=contract_ids[i] if contract_ids and i < len(contract_ids) else None,
        )
        for i in range(n_agents)
    ]
    if serial:
        results = []
        for c in coros:
            results.append(await c)
        return results
    return await asyncio.gather(*coros)


def main() -> int:
    parser = argparse.ArgumentParser(description="多 Agent 并发 + 断线重连内测")
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--agents", type=int, default=3)
    parser.add_argument("--built-in", action="store_true", help="内置 ASGI 模式（无需起服务）")
    args = parser.parse_args()

    if args.built_in:
        os.environ.setdefault("SKILLOS_DATABASE_URL", "sqlite://")
        from fastapi import FastAPI

        from skillos.web_api import api_router

        app = FastAPI()
        app.include_router(api_router)

        results = asyncio.run(_run_builtin(app, args.agents))
    else:
        results = asyncio.run(run_demo(args.url, args.agents))

    print("=" * 66)
    print(f"多 Agent 并发 + 断线重连内测：{len(results)} 个 Agent")
    for r in results:
        verdict = "GO ✅" if r.get("ok") else "NO-GO ❌"
        print(f"  {r['identity']:16s} contract={r.get('contract_id') or '-'}  {verdict}")
    ok = all(r.get("ok") for r in results)
    print("=" * 66)
    print(f"并发内测验收: {'GO ✅' if ok else 'NO-GO ❌'}")
    return 0 if ok else 1


async def _run_builtin(app, n_agents: int) -> list[dict]:
    """内置模式：先造一个 open 契约，再并发跑 N 个 Agent。"""
    import httpx

    from skillos.market.outcome_contracts import OutcomeContractService
    from skillos.security.message_signer import MessageSigner

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
        business = MessageSigner(signer_id="business-conc")
        r = await c.post(
            "/api/v1/onboarding/register",
            json={
                "identity_id": "business-conc",
                "role": "consumer",
                "public_key_pem": business._public_key_pem,
            },
        )
        assert r.status_code == 200

        from skillos.db.engine import get_sessionmaker

        session = get_sessionmaker()()
        svc = OutcomeContractService(session)
        ids = []
        for i in range(n_agents):
            ctr = svc.create(f"business-conc-{i}", "做内容运营并分发", base_price=4000.0)
            svc.select_tier(ctr.id, "balanced")
            ids.append(ctr.id)
        session.commit()
        session.close()

        return await run_demo(
            "http://testserver", n_agents, contract_ids=ids, transport=httpx.ASGITransport(app=app)
        )


if __name__ == "__main__":
    raise SystemExit(main())
