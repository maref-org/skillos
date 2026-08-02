"""Tests for M8-P1.2 — 租户开通 API + 契约创建租户校验。"""

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillos.security.message_signer import MessageSigner
from skillos.web_api.onboarding import router as onboarding_router
from skillos.web_api.outcome import router as outcome_router
from skillos.web_api.tenants import router as tenants_router


def _build_client():
    app = FastAPI()
    app.include_router(onboarding_router)
    app.include_router(tenants_router)
    app.include_router(outcome_router)
    return TestClient(app)


@pytest.fixture
def client(db_session):
    return _build_client()


def _register(client, identity_id):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    r = client.post(
        "/onboarding/register",
        json={"identity_id": identity_id, "role": "consumer", "public_key_pem": pem},
    )
    assert r.status_code == 200
    return MessageSigner(signer_id=identity_id, private_key=key)


def _signed_post(client, signer, path, payload):
    headers = signer.sign_headers(payload)
    return client.post(path, json=payload, headers=headers)


def _signed_put(client, signer, path, payload):
    headers = signer.sign_headers(payload)
    return client.put(path, json=payload, headers=headers)


class TestTenantOnboardingApi:
    def test_create_tenant(self, client):
        signer = _register(client, "req-tenant-1")
        r = _signed_post(
            client,
            signer,
            "/tenants",
            {"tenant_id": "tenant-api-1", "name": "内容运营事业部", "scene_config": {"template": "内容代运营"}},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        assert body["tenant"]["tenant_id"] == "tenant-api-1"
        assert body["tenant"]["status"] == "draft"

    def test_create_tenant_idempotent(self, client):
        signer = _register(client, "req-tenant-2")
        payload = {"tenant_id": "tenant-api-2", "name": "重复开通"}
        r1 = _signed_post(client, signer, "/tenants", payload)
        r2 = _signed_post(client, signer, "/tenants", payload)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r2.json()["tenant"]["tenant_id"] == "tenant-api-2"

    def test_requires_signature(self, client):
        r = client.post("/tenants", json={"tenant_id": "tenant-anon", "name": "匿名"})
        assert r.status_code == 401

    def test_get_tenant(self, client):
        signer = _register(client, "req-tenant-3")
        _signed_post(client, signer, "/tenants", {"tenant_id": "tenant-api-3", "name": "查询"})
        r = client.get("/tenants/tenant-api-3")
        assert r.status_code == 200
        assert r.json()["tenant"]["name"] == "查询"
        r404 = client.get("/tenants/tenant-missing")
        assert r404.status_code == 404

    def test_list_tenants(self, client):
        signer = _register(client, "req-tenant-4")
        _signed_post(client, signer, "/tenants", {"tenant_id": "tenant-api-4a", "name": "A"})
        _signed_post(client, signer, "/tenants", {"tenant_id": "tenant-api-4b", "name": "B"})
        r = client.get("/tenants")
        assert r.status_code == 200
        ids = [t["tenant_id"] for t in r.json()["tenants"]]
        assert "tenant-api-4a" in ids and "tenant-api-4b" in ids

    def test_update_scene_config(self, client):
        signer = _register(client, "req-tenant-5")
        _signed_post(client, signer, "/tenants", {"tenant_id": "tenant-api-5", "name": "改配置"})
        r = _signed_put(
            client,
            signer,
            "/tenants/tenant-api-5/scene",
            {"scene_config": {"template": "短视频矩阵", "tier": "sprint"}},
        )
        assert r.status_code == 200, r.text
        assert r.json()["tenant"]["scene_config"] == {"template": "短视频矩阵", "tier": "sprint"}

    def test_activate_tenant(self, client):
        signer = _register(client, "req-tenant-6")
        _signed_post(client, signer, "/tenants", {"tenant_id": "tenant-api-6", "name": "激活"})
        r = _signed_post(client, signer, "/tenants/tenant-api-6/activate", {})
        assert r.status_code == 200, r.text
        assert r.json()["tenant"]["status"] == "active"

    def test_activate_missing_tenant_404(self, client):
        signer = _register(client, "req-tenant-7")
        r = _signed_post(client, signer, "/tenants/tenant-missing/activate", {})
        assert r.status_code == 404


class TestContractTenantValidation:
    REQ_TEXT = "给公众号做 30 天内容运营并分发"

    def test_contract_with_active_tenant(self, client):
        signer = _register(client, "req-val-1")
        _signed_post(client, signer, "/tenants", {"tenant_id": "tenant-val-1", "name": "激活租户"})
        _signed_post(client, signer, "/tenants/tenant-val-1/activate", {})
        r = _signed_post(
            client,
            signer,
            "/outcome/contracts",
            {"requirement_text": self.REQ_TEXT, "tenant_id": "tenant-val-1"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["contract"]["tenant_id"] == "tenant-val-1"

    def test_contract_with_draft_tenant_rejected(self, client):
        signer = _register(client, "req-val-2")
        _signed_post(client, signer, "/tenants", {"tenant_id": "tenant-val-2", "name": "未激活"})
        r = _signed_post(
            client,
            signer,
            "/outcome/contracts",
            {"requirement_text": self.REQ_TEXT, "tenant_id": "tenant-val-2"},
        )
        assert r.status_code == 422
        assert "active" in r.json()["detail"]

    def test_contract_with_unknown_tenant_rejected(self, client):
        signer = _register(client, "req-val-3")
        r = _signed_post(
            client,
            signer,
            "/outcome/contracts",
            {"requirement_text": self.REQ_TEXT, "tenant_id": "tenant-ghost"},
        )
        assert r.status_code == 422

    def test_contract_without_tenant_ok(self, client):
        signer = _register(client, "req-val-4")
        r = _signed_post(
            client,
            signer,
            "/outcome/contracts",
            {"requirement_text": self.REQ_TEXT},
        )
        assert r.status_code == 200
        assert r.json()["contract"]["tenant_id"] is None


class TestTenantPayoutQuotaApi:
    def test_set_quota(self, client):
        signer = _register(client, "req-quota-1")
        _signed_post(client, signer, "/tenants", {"tenant_id": "tenant-quota-1", "name": "限额定"})
        r = _signed_put(client, signer, "/tenants/tenant-quota-1/quota", {"payout_limit": 50000})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["tenant"]["payout_limit"] == 50000
        assert body["usage"] == {"limit": 50000.0, "used": 0.0, "remaining": 50000.0}

    def test_quota_requires_signature(self, client):
        r = client.put("/tenants/tenant-quota-x/quota", json={"payout_limit": 100})
        assert r.status_code == 401

    def test_set_quota_missing_tenant_404(self, client):
        signer = _register(client, "req-quota-2")
        r = _signed_put(client, signer, "/tenants/tenant-missing/quota", {"payout_limit": 100})
        assert r.status_code == 404

    def test_negative_quota_rejected(self, client):
        signer = _register(client, "req-quota-3")
        _signed_post(client, signer, "/tenants", {"tenant_id": "tenant-quota-3", "name": "负"})
        r = _signed_put(client, signer, "/tenants/tenant-quota-3/quota", {"payout_limit": -5})
        assert r.status_code == 422

    def test_tenant_serialization_includes_quota(self, client):
        signer = _register(client, "req-quota-4")
        _signed_post(client, signer, "/tenants", {"tenant_id": "tenant-quota-4", "name": "序列化"})
        r = client.get("/tenants/tenant-quota-4")
        assert r.status_code == 200
        t = r.json()["tenant"]
        assert t["payout_limit"] == 0.0
        assert t["payout_used"] == 0.0


class TestTenantOwnerGuard:
    """I2 — 租户写操作仅 owner 可执行。"""

    def test_non_owner_cannot_modify_scene(self, client):
        owner = _register(client, "owner-1")
        intruder = _register(client, "intruder-1")
        _signed_post(client, owner, "/tenants", {"tenant_id": "tenant-own-1", "name": "有主租户"})
        r = _signed_put(client, intruder, "/tenants/tenant-own-1/scene", {"scene_config": {"template": "hacked"}})
        assert r.status_code == 403
        assert "owner" in r.json()["detail"]

    def test_non_owner_cannot_set_quota(self, client):
        owner = _register(client, "owner-2")
        intruder = _register(client, "intruder-2")
        _signed_post(client, owner, "/tenants", {"tenant_id": "tenant-own-2", "name": "限额定"})
        r = _signed_put(client, intruder, "/tenants/tenant-own-2/quota", {"payout_limit": 100000})
        assert r.status_code == 403

    def test_owner_can_modify(self, client):
        owner = _register(client, "owner-3")
        _signed_post(client, owner, "/tenants", {"tenant_id": "tenant-own-3", "name": "自有"})
        r = _signed_put(client, owner, "/tenants/tenant-own-3/scene", {"scene_config": {"template": "短视频矩阵"}})
        assert r.status_code == 200, r.text
        assert r.json()["tenant"]["scene_config"]["template"] == "短视频矩阵"
