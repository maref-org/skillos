#!/usr/bin/env python3
"""外部 Agent 接入演示 + 垂直场景内测 — 内容 IP 代运营成果契约闭环

模拟一个真实外部 Agent 构建者（如 OpenClaw / Claude Code 用户）接入 SkillOS：

  1. 注册 Ed25519 身份（外部 Agent 构建者）
  2. 需求方（企业主）提需求 → 三方案报价 → 选档
  3. 外部 Agent 浏览可承接契约（list_open_contracts）
  4. 承接当项目长（accept_contract）
  5. 组队技能作者 → 交付（L3 合规存证）
  6. 验收 + 超预期小费 → 结算 → 出款指令提交（持牌桥 sandbox）

运行::
    # 内置模式（TestClient，无需起服务）
    .venv/bin/python scripts/external_agent_demo.py

    # 真实服务模式（先起服务，再跑 demo）
    .venv/bin/python scripts/run_server.py --port 8080 &
    .venv/bin/python scripts/external_agent_demo.py --real-server --url http://127.0.0.1:8080

红线：不托管真实资金，出款指令仅记账（sandbox 模拟持牌执行），法币由下游持牌平台执行。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _build_signer(identity_id: str):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from skillos.security.message_signer import MessageSigner

    key = Ed25519PrivateKey.generate()
    pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return MessageSigner(signer_id=identity_id, private_key=key), pem


def _build_inmemory():
    """内置模式：TestClient（无需起服务）。"""
    import os

    os.environ.setdefault("SKILLOS_DATABASE_URL", "sqlite://")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from skillos.web_api.agent import router as agent_router
    from skillos.web_api.onboarding import router as onboarding_router
    from skillos.web_api.outcome import router as outcome_router
    from skillos.web_api.payments import router as payments_router

    app = FastAPI()
    for r in (onboarding_router, outcome_router, agent_router, payments_router):
        app.include_router(r)
    return TestClient(app)


class _Runner:
    """演示运行器：封装 TestClient 或真实 HTTP 客户端。"""

    def __init__(self, client, base_url: str = ""):
        self._client = client
        self._base_url = base_url

    def post(self, path: str, json: dict, headers: dict | None = None):
        if self._base_url:
            import httpx

            return httpx.post(f"{self._base_url}/api/v1{path}", json=json, headers=headers or {})
        return self._client.post(path, json=json, headers=headers or {})

    def get(self, path: str):
        if self._base_url:
            import httpx

            return httpx.get(f"{self._base_url}/api/v1{path}")
        return self._client.get(path)


def main() -> int:
    import os

    parser = argparse.ArgumentParser(description="SkillOS 外部 Agent 接入演示")
    parser.add_argument("--real-server", action="store_true", help="走真实 HTTP 服务（需先起 run_server.py）")
    parser.add_argument("--url", default=os.environ.get("SKILLOS_URL", "http://127.0.0.1:8080"))
    args = parser.parse_args()

    real = args.real_server
    if real:
        import httpx

        runner = _Runner(None, base_url=args.url)
        # 健康检查
        try:
            httpx.get(f"{args.url}/health").raise_for_status()
        except Exception as exc:
            print(f"ERROR: 无法连接真实服务 {args.url}（请先运行 scripts/run_server.py）: {exc}")
            return 1
    else:
        runner = _Runner(_build_inmemory())

    def _register(identity_id: str, role: str = "consumer"):
        signer, pem = _build_signer(identity_id)
        r = runner.post("/onboarding/register", json={"identity_id": identity_id, "role": role, "public_key_pem": pem})
        if r.status_code not in (200, 409):
            print(f"ERROR register {identity_id}: {r.status_code} {r.text}")
            sys.exit(1)
        return signer

    def _signed_post(signer, path: str, payload: dict):
        if real:
            return runner.post(path, json=payload, headers=signer.sign_headers_http(payload))
        return runner.post(path, json=payload, headers=signer.sign_headers(payload))

    print("=" * 62)
    print("SkillOS 成果契约闭环 · 外部 Agent 接入演示 + 垂直场景内测")
    print(f"连接模式: {'真实 HTTP (' + args.url + ')' if real else '内置 TestClient'}")
    print("垂直场景: 内容 IP 代运营 | 角色: 企业主 / 外部 Agent 构建者 / 技能作者")
    print("=" * 62)

    # 1. 外部 Agent 构建者注册（provider 身份）
    agent = _register("agent-demo", role="provider")
    print("\n[1/7] 外部 Agent 构建者注册 Ed25519 身份 -> agent-demo")

    # 2. 企业主提需求 + 三方案报价
    business = _register("business-demo")
    req = "我要给公司公众号做 30 天内容运营，写文章并分发到多平台，最后要复盘"
    r = _signed_post(business, "/outcome/contracts", {"requirement_text": req})
    assert r.status_code == 200, r.text
    body = r.json()
    cid = body["contract"]["id"]
    print(f"\n[2/7] 企业主提需求，生成三方案报价（{len(body['plans'])} 档）:")
    for p in body["plans"]:
        print(
            f"      {p['tier']:8s} 成功率 {int(p['success_rate'] * 100)}%  ¥{p['price']:>7.0f}  {p['delivery_days']}天"
        )

    # 3. 企业主选 B 均衡档
    r = _signed_post(business, f"/outcome/contracts/{cid}/select-tier", {"tier": "balanced"})
    assert r.status_code == 200, r.text
    print(f"[3/7] 企业主选档 balanced（成功率 85%，¥{r.json()['contract']['price']:.0f}）")

    # 4. 外部 Agent 浏览可承接契约
    r = runner.get("/agent/list_open_contracts")
    assert r.json()["total"] == 1, r.text
    print(f"[4/7] 外部 Agent 浏览可承接契约 -> 发现 {r.json()['total']} 份 open")

    # 5. 外部 Agent 承接当项目长
    r = _signed_post(agent, "/agent/accept_contract", {"contract_id": cid})
    assert r.status_code == 200, r.text
    print("[5/7] 外部 Agent 承接契约成为项目长（contractor = agent-demo）")

    # 组队 + 交付
    from skillos.db.engine import get_sessionmaker
    from skillos.market.outcome_contracts import OutcomeContractService

    session = get_sessionmaker()()
    service = OutcomeContractService(session)
    service.create_service_team(cid, "agent-demo", [{"member_id": "author-demo", "share_ratio": 0.4}])
    session.commit()

    r = _signed_post(
        agent,
        f"/outcome/contracts/{cid}/submit-delivery",
        {"evidence_text": "已完成 30 天内容日历与 12 篇图文，合规检查通过"},
    )
    assert r.status_code == 200, r.text
    print("      交付成功（L3 合规存证 evidence_hash = %s）" % r.json()["contract"]["evidence_hash"])

    # 6. 验收 + 小费
    r = _signed_post(business, f"/outcome/contracts/{cid}/confirm", {"accepted": True, "tip_ratio": 0.15})
    assert r.status_code == 200, r.text
    tip = r.json()["tip"]
    print(f"[6/7] 企业主验收通过 + 超预期小费 ¥{tip['amount']:.0f}（15%）")

    # 7. 结算 + 出款指令提交（持牌桥 sandbox）
    settled = service.settle(cid)
    session.commit()
    print(
        f"[7/7] 结算 ¥{settled['amount']:.0f}（平台费 ¥{settled['platform_fee']:.0f}，"
        f"保证金 {settled['deposit_status']}）"
    )
    r = _signed_post(business, f"/payments/contracts/{cid}/submit", {"provider": "sandbox"})
    assert r.status_code == 200, r.text
    payout = r.json()
    print(f"      出款提交 -> 持牌桥 {payout['provider']}（流水号 {payout['external_ref']}，状态 {payout['status']}）:")
    for i in payout["instructions"]:
        print(f"      - {i['payee_id']:22s} {i['role']:12s} ¥{i['amount']:>8.2f}  {i['status']}  {i['external_ref']}")

    # Go / No-Go 判定
    contract = service.get(cid)
    ok = all(
        [
            contract.status == "paid",
            contract.deposit_status == "released",
            payout["status"] == "succeeded",
            all(i["status"] == "executed" for i in payout["instructions"]),
        ]
    )
    verdict = "GO ✅" if ok else "NO-GO ❌"
    print("\n" + "=" * 62)
    print(f"验收判定: {verdict}  状态={contract.status}  保证金={contract.deposit_status}")
    print("=" * 62)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
