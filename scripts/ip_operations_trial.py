#!/usr/bin/env python3
"""内容 IP 代运营垂直场景 · 内测 CLI

一键跑「内容 IP 代运营」垂直场景的成果契约闭环：
  企业主提需求 → 三方案报价 → 选档 → 外部 Agent 承接 → 组队 → 交付（L3 存证）
  → 验收 + 小费 → 结算 → 出款指令提交（持牌桥 sandbox）→ GO/NO-GO

运行::
    # 内置模式（内存 DB + TestClient）
    .venv/bin/python scripts/ip_operations_trial.py

    # 指定场景模板 / 档位 / 小费
    .venv/bin/python scripts/ip_operations_trial.py --scenario 短视频矩阵 --tier sprint --tip 0.20

    # 真实服务模式（先起服务）
    .venv/bin/python scripts/run_server.py --port 8080 &
    .venv/bin/python scripts/ip_operations_trial.py --real-server --url http://127.0.0.1:8080
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skillos.scenarios.ip_operations import TEMPLATES, IpTrialScenario


def main() -> int:
    import os

    parser = argparse.ArgumentParser(description="内容 IP 代运营垂直场景内测")
    parser.add_argument("--scenario", default="内容代运营", choices=list(TEMPLATES), help="场景模板")
    parser.add_argument("--tier", default="balanced", choices=["stable", "balanced", "sprint"])
    parser.add_argument("--tip", type=float, default=0.15)
    parser.add_argument("--real-server", action="store_true", help="走真实 HTTP 服务")
    parser.add_argument("--url", default=os.environ.get("SKILLOS_URL", "http://127.0.0.1:8080"))
    args = parser.parse_args()

    scenario = IpTrialScenario.build(args.scenario, tier=args.tier, tip_ratio=args.tip)

    if args.real_server:
        import httpx

        base = args.url
        try:
            httpx.get(f"{base}/health").raise_for_status()
        except Exception as exc:
            print(f"ERROR: 无法连接真实服务 {base}（请先运行 scripts/run_server.py）: {exc}")
            return 1
        runner = _RealRunner(base)
        prefix = "/api/v1"
    else:
        os.environ.setdefault("SKILLOS_DATABASE_URL", "sqlite://")
        runner = _InMemoryRunner()
        prefix = ""

    # ── 身份注册 ─────────────────────────────────────────────────────────
    business = _signer_and_register(runner, prefix, "business-trial", "consumer")
    agent = _signer_and_register(runner, prefix, "agent-trial", "provider")

    print("=" * 66)
    print(f"内容 IP 代运营 · 垂直场景内测 —— 模板「{scenario.name}」")
    print(f"连接模式: {'真实 HTTP (' + args.url + ')' if args.real_server else '内置 TestClient'}")
    print(f"角色: 企业主 / 外部 Agent（项目长）/ 技能作者  档位: {scenario.tier}  小费: {int(scenario.tip_ratio*100)}%")
    print("=" * 66)

    # ── 1. 提需求 + 三方案报价 ───────────────────────────────────────────
    req_payload = {"requirement_text": scenario.requirement}
    r = _signed(runner, business, f"{prefix}/outcome/contracts", req_payload, real=args.real_server)
    assert r.status_code == 200, r.text
    body = r.json()
    cid = body["contract"]["id"]
    print(f"\n[1/5] 企业主提需求「{scenario.requirement[:40]}…」→ 三方案报价:")
    for p in body["plans"]:
        print(f"      {p['tier']:8s} 成功率 {int(p['success_rate']*100)}%  ¥{p['price']:>7.0f}  {p['delivery_days']}天")

    # ── 2. 选档 ──────────────────────────────────────────────────────────
    tier_payload = {"tier": scenario.tier}
    r = _signed(runner, business, f"{prefix}/outcome/contracts/{cid}/select-tier", tier_payload, real=args.real_server)
    assert r.status_code == 200, r.text
    print(f"[2/5] 企业主选档 {scenario.tier}（price ¥{r.json()['contract']['price']:.0f}）")

    # ── 3. 外部 Agent 浏览 + 承接 ────────────────────────────────────────
    r = runner.get(f"{prefix}/agent/list_open_contracts")
    assert any(c["id"] == cid for c in r.json()["contracts"])
    accept_payload = {"contract_id": cid}
    r = _signed(runner, agent, f"{prefix}/agent/accept_contract", accept_payload, real=args.real_server)
    assert r.status_code == 200, r.text
    print("[3/5] 外部 Agent 浏览并承接契约，成为项目长（contractor = agent-trial）")

    # ── 4. 组队 + 交付 + 验收 + 小费 ─────────────────────────────────────
    _seed_team(cid, args.real_server, scenario, runner=runner, agent=agent, prefix=prefix)
    evidence = f"已完成「{scenario.name}」场景交付物：内容策略/图文/分发/复盘，合规检查通过"
    del_payload = {"evidence_text": evidence}
    r = _signed(runner, agent, f"{prefix}/outcome/contracts/{cid}/submit-delivery", del_payload, real=args.real_server)
    assert r.status_code == 200, r.text
    print(f"      交付成功（L3 合规存证 evidence_hash = {r.json()['contract']['evidence_hash']}）")

    confirm_payload = {"accepted": True, "tip_ratio": scenario.tip_ratio}
    r = _signed(runner, business, f"{prefix}/outcome/contracts/{cid}/confirm", confirm_payload, real=args.real_server)
    assert r.status_code == 200, r.text
    print(f"[4/5] 企业主验收通过 + 超预期小费 ¥{r.json()['tip']['amount']:.0f}（{int(scenario.tip_ratio*100)}%）")

    # ── 5. 结算 + 出款提交（持牌桥 sandbox） ────────────────────────────
    _settle(cid, args.real_server)
    r = runner.post(f"{prefix}/payments/contracts/{cid}/submit", json={"provider": "sandbox"})
    assert r.status_code == 200, r.text
    payout = r.json()
    print(
        f"[5/5] 结算完成 → 出款提交 持牌桥 {payout['provider']}（流水号 "
        f"{payout['external_ref']}，{payout['status']}）:"
    )
    for i in payout["instructions"]:
        print(f"      - {i['payee_id']:22s} {i['role']:12s} ¥{i['amount']:>8.2f}  {i['status']}  {i['external_ref']}")

    # ── GO / NO-GO ────────────────────────────────────────────────────────
    status, deposit = _final_status(cid, args.real_server)
    ok = all(
        [
            status == "paid",
            deposit == "released",
            payout["status"] == "succeeded",
            all(i["status"] == "executed" for i in payout["instructions"]),
        ]
    )
    verdict = "GO ✅" if ok else "NO-GO ❌"
    print("\n" + "=" * 66)
    print(f"内测验收: {verdict}  状态={status}  保证金={deposit}")
    print("=" * 66)
    return 0 if ok else 1


# ── 客户端抽象 ────────────────────────────────────────────────────────────

class _InMemoryRunner:
    """内置模式：TestClient（无需起服务）。"""

    def __init__(self):
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
        self._client = TestClient(app)

    def post(self, path, json, headers=None):
        return self._client.post(path, json=json, headers=headers or {})

    def get(self, path):
        return self._client.get(path)


class _RealRunner:
    """真实 HTTP 模式。"""

    def __init__(self, base: str):
        self._base = base

    def post(self, path, json, headers=None):
        import httpx

        return httpx.post(f"{self._base}{path}", json=json, headers=headers or {})

    def get(self, path):
        import httpx

        return httpx.get(f"{self._base}{path}")


# ── 工具函数 ──────────────────────────────────────────────────────────────

def _signer_and_register(runner, prefix, identity_id, role):
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
    signer = MessageSigner(signer_id=identity_id, private_key=key)
    reg_payload = {"identity_id": identity_id, "role": role, "public_key_pem": pem}
    r = runner.post(f"{prefix}/onboarding/register", json=reg_payload)
    if r.status_code not in (200, 409):
        raise RuntimeError(f"register {identity_id} failed: {r.status_code} {r.text}")
    return signer


def _signed(runner, signer, path, payload, real: bool):
    headers = signer.sign_headers_http(payload) if real else signer.sign_headers(payload)
    return runner.post(path, json=payload, headers=headers)


def _seed_team(cid: str, real: bool, scenario: IpTrialScenario, runner=None, agent=None, prefix=""):
    if real:
        # 真实模式：通过 HTTP 组队端点（contractor 签名身份），替代直连 DB
        team_payload = {"contract_id": cid, "members": scenario.team_members}
        r = _signed(runner, agent, f"{prefix}/agent/contracts/{cid}/team", team_payload, real=True)
        assert r.status_code == 200, r.text
        assert r.json().get("success"), r.text
        print("      外部 Agent 组队成功（HTTP 端点）")
        return
    from skillos.db.engine import get_sessionmaker
    from skillos.market.outcome_contracts import OutcomeContractService

    session = get_sessionmaker()()
    svc = OutcomeContractService(session)
    svc.create_service_team(cid, "agent-trial", scenario.team_members)
    session.commit()


def _settle(cid: str, real: bool):
    from skillos.db.engine import get_sessionmaker
    from skillos.market.outcome_contracts import OutcomeContractService

    session = get_sessionmaker()()
    svc = OutcomeContractService(session)
    svc.settle(cid)
    session.commit()


def _final_status(cid: str, real: bool):
    from skillos.db.engine import get_sessionmaker
    from skillos.market.outcome_contracts import OutcomeContractService

    session = get_sessionmaker()()
    contract = OutcomeContractService(session).get(cid)
    return contract.status, contract.deposit_status


if __name__ == "__main__":
    raise SystemExit(main())
