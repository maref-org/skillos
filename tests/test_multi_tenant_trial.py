"""Tests for M7-P4.4 — 多租户并发内测脚本冒烟。"""



def test_multi_tenant_trial_smoke():
    """内置模式跑 2 个租户，各租户数据隔离，整体 GO。"""
    from scripts.multi_tenant_trial import run_multi_tenant

    result = run_multi_tenant(tenant_ids=["tenant-a", "tenant-b"])
    assert result["verdict"] is True
    assert len(result["rows"]) == 2
    assert all(r["ok"] for r in result["rows"])
    assert {r["tenant_id"] for r in result["rows"]} == {"tenant-a", "tenant-b"}
    assert result["isolation"]["ok"] is True


def test_multi_tenant_trial_isolates_contracts():
    """契约按 tenant_id 隔离查询。"""
    from scripts.multi_tenant_trial import run_multi_tenant

    result = run_multi_tenant(tenant_ids=["tenant-x", "tenant-y"])
    assert result["verdict"] is True
    by_tenant = {r["tenant_id"]: r for r in result["rows"]}
    assert by_tenant["tenant-x"]["cid"] != by_tenant["tenant-y"]["cid"]
    per_tenant = result["isolation"]["per_tenant"]
    assert per_tenant["tenant-x"] >= 1
    assert per_tenant["tenant-y"] >= 1


def test_multi_tenant_trial_single_tenant():
    """单租户也能跑。"""
    from scripts.multi_tenant_trial import run_multi_tenant

    result = run_multi_tenant(tenant_ids=["tenant-solo"])
    assert result["verdict"] is True
    assert len(result["rows"]) == 1
