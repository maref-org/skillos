"""P4.1 租户模型 + 契约带 tenant_id 的测试"""

import pytest


def test_create_tenant_and_contract(db_session):
    """建租户 + 契约带 tenant_id 落库。"""
    from skillos.market.outcome_contracts import OutcomeContractService
    from skillos.market.tenants import TenantService

    tsvc = TenantService(db_session)
    tenant = tsvc.create("tenant-ops", "内容代运营事业部", scene_config={"template": "内容代运营"})
    assert tenant.tenant_id == "tenant-ops"
    assert tenant.name == "内容代运营事业部"
    assert tenant.scene_config == {"template": "内容代运营"}

    osvc = OutcomeContractService(db_session)
    contract = osvc.create("requester-a", "做内容代运营并分发", base_price=4000.0, tenant_id="tenant-ops")
    assert contract.tenant_id == "tenant-ops"
    stored = osvc.get(contract.id)
    assert stored.tenant_id == "tenant-ops"


def test_tenant_crud(db_session):
    """TenantService get/list/update_scene_config。"""
    from skillos.market.tenants import TenantService

    svc = TenantService(db_session)
    svc.create("tenant-a", "事业部A", scene_config={"template": "短视频矩阵"})
    svc.create("tenant-b", "事业部B")

    assert svc.get("tenant-a").name == "事业部A"
    assert [t.tenant_id for t in svc.list()] == ["tenant-a", "tenant-b"]
    assert svc.get("tenant-a").scene_config == {"template": "短视频矩阵"}

    svc.update_scene_config("tenant-a", {"template": "知识付费专栏", "tip_max_ratio": 0.2})
    assert svc.get("tenant-a").scene_config == {"template": "知识付费专栏", "tip_max_ratio": 0.2}

    with pytest.raises(ValueError):
        svc.get("tenant-unknown")


def test_contract_without_tenant_defaults_none(db_session):
    """契约不传 tenant_id 时默认 None。"""
    from skillos.market.outcome_contracts import OutcomeContractService

    osvc = OutcomeContractService(db_session)
    contract = osvc.create("requester-b", "写一篇公众号文章")
    assert contract.tenant_id is None


def test_tenant_status_defaults_draft(db_session):
    """租户默认 draft 状态。"""
    from skillos.market.tenants import TenantService

    svc = TenantService(db_session)
    svc.create("tenant-st-1", "状态默认")
    assert svc.get("tenant-st-1").status == "draft"


def test_tenant_set_status_flow(db_session):
    """set_status 流转 draft → active → inactive。"""
    from skillos.market.tenants import TenantService

    svc = TenantService(db_session)
    svc.create("tenant-st-2", "状态流转", status="draft")
    svc.set_status("tenant-st-2", "active")
    assert svc.get("tenant-st-2").status == "active"
    svc.set_status("tenant-st-2", "inactive")
    assert svc.get("tenant-st-2").status == "inactive"


def test_tenant_set_status_invalid_raises(db_session):
    """非法状态值被拒绝。"""
    from skillos.market.tenants import TenantService

    svc = TenantService(db_session)
    svc.create("tenant-st-3", "非法状态")
    with pytest.raises(ValueError, match="Invalid tenant status"):
        svc.set_status("tenant-st-3", "bogus")


def test_tenant_create_with_status(db_session):
    """create 支持直接指定状态。"""
    from skillos.market.tenants import TenantService

    svc = TenantService(db_session)
    tenant = svc.create("tenant-st-4", "直接激活", status="active")
    assert tenant.status == "active"
