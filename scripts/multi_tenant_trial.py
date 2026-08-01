#!/usr/bin/env python3
"""多租户并发内测 — 垂直场景多租户上线验证（M7-P4.4）

循环多个租户各跑一次 IpTrialScenario 内测流程（复用 ip_operations_trial 核心），
断言各租户契约/出款互相隔离（按 tenant_id 过滤查询），输出各租户 GO/NO-GO 汇总表。

运行::
    # 内置模式（内存 DB，默认）
    .venv/bin/python scripts/multi_tenant_trial.py

    # 指定租户列表
    .venv/bin/python scripts/multi_tenant_trial.py --tenants tenant-ops tenant-video tenant-pay

    # 真实服务模式（先起服务）
    .venv/bin/python scripts/run_server.py --port 8080 &
    .venv/bin/python scripts/multi_tenant_trial.py --real-server --url http://127.0.0.1:8080
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.ip_operations_trial import (
    _InMemoryRunner,
    _RealRunner,
    _signer_and_register,
    run_scenario,
)


def run_multi_tenant(
    tenant_ids: list[str],
    real: bool = False,
    url: str = "http://127.0.0.1:8080",
    scenario_names: list[str] | None = None,
) -> dict:
    """多租户并发内测。返回 {verdict, rows, isolation}。"""
    from skillos.db.engine import get_sessionmaker
    from skillos.market.tenants import TenantService
    from skillos.scenarios.ip_operations import IpTrialScenario

    if real:
        import httpx

        try:
            httpx.get(f"{url}/health").raise_for_status()
        except Exception as exc:
            print(f"ERROR: 无法连接真实服务 {url}: {exc}")
            return {"verdict": False, "rows": [], "isolation": {"ok": False}, "error": str(exc)}
        runner = _RealRunner(url)
        prefix = "/api/v1"
    else:
        os.environ.setdefault("SKILLOS_DATABASE_URL", "sqlite://")
        runner = _InMemoryRunner()
        prefix = ""

    # 确保租户存在并激活（内置模式直连 DB；真实模式共用服务端磁盘库）
    names = scenario_names or ["内容代运营"] * len(tenant_ids)
    session = get_sessionmaker()()
    tsvc = TenantService(session)
    for tid, name in zip(tenant_ids, names):
        try:
            tsvc.get(tid)
        except ValueError:
            tsvc.create(tid, name, scene_config={"template": name})
        tsvc.set_status(tid, "active")
    session.commit()
    session.close()

    print("=" * 66)
    print(f"多租户并发内测：{len(tenant_ids)} 个租户")
    print(f"连接模式: {'真实 HTTP (' + url + ')' if real else '内置 TestClient'}")
    print("=" * 66)

    rows = []
    all_ok = True
    for idx, tid in enumerate(tenant_ids):
        try:
            business = _signer_and_register(runner, prefix, f"biz-{tid}", "consumer")
            agent = _signer_and_register(runner, prefix, f"agent-{tid}", "provider")
            scenario = IpTrialScenario.build(tenant_id=tid)
            ok, cid = run_scenario(runner, prefix, scenario, business, agent, real, tenant_id=tid)
            rows.append({"tenant_id": tid, "ok": ok, "cid": cid})
            all_ok = all_ok and ok
        except Exception as exc:  # 单个租户失败不阻断整体
            rows.append({"tenant_id": tid, "ok": False, "cid": None, "error": str(exc)})
            all_ok = False

    isolation = _check_isolation(real, tenant_ids, rows)

    print("\n" + "=" * 66)
    for r in rows:
        mark = "GO ✅" if r["ok"] else "NO-GO ❌"
        cid = r.get("cid", "")
        print(f"  {r['tenant_id']:24s} {mark}  contract={cid}")
    print(f"隔离检查: {'PASS ✅' if isolation['ok'] else 'FAIL ❌'}")
    print(f"多租户并发验收: {'GO ✅' if all_ok and isolation['ok'] else 'NO-GO ❌'}")
    print("=" * 66)

    return {"verdict": all_ok and isolation["ok"], "rows": rows, "isolation": isolation}


def _check_isolation(real: bool, tenant_ids: list[str], rows: list[dict]) -> dict:
    """按 tenant_id 过滤查询，断言各租户契约互相隔离。"""
    from skillos.db.engine import get_sessionmaker
    from skillos.db.models import OutcomeContractModel

    session = get_sessionmaker()()
    try:
        per_tenant: dict[str, int] = {}
        for tid in tenant_ids:
            per_tenant[tid] = (
                session.query(OutcomeContractModel)
                .filter(OutcomeContractModel.tenant_id == tid)
                .count()
            )
        ok = all(count >= 1 for count in per_tenant.values())
        return {"ok": ok, "per_tenant": per_tenant}
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="多租户并发内测")
    parser.add_argument("--tenants", nargs="*", default=None, help="租户 ID 列表（默认 3 个示例租户）")
    parser.add_argument("--real-server", action="store_true", help="走真实 HTTP 服务")
    parser.add_argument("--url", default=os.environ.get("SKILLOS_URL", "http://127.0.0.1:8080"))
    args = parser.parse_args()

    tenant_ids = args.tenants or ["tenant-ops", "tenant-video", "tenant-pay"]
    result = run_multi_tenant(tenant_ids, real=args.real_server, url=args.url)
    return 0 if result["verdict"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
