"""Tests for Phase D — Agent MCP-style endpoints (Ed25519 signed)."""

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillos.market.api import router as market_router
from skillos.security.message_signer import MessageSigner
from skillos.web_api.agent import router as agent_router
from skillos.web_api.onboarding import router as onboarding_router
from skillos.web_api.protocol import router as protocol_router


def _build_client():
    app = FastAPI()
    app.include_router(market_router)
    app.include_router(onboarding_router)
    app.include_router(protocol_router)
    app.include_router(agent_router)
    return TestClient(app)


@pytest.fixture
def client(db_session):
    return _build_client()


def _register_identity(client, identity_id):
    """注册一个自持 Ed25519 keypair 的身份，返回可签名的 MessageSigner。"""
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
        json={"identity_id": identity_id, "role": "provider", "public_key_pem": pem},
    )
    assert r.status_code == 200
    return MessageSigner(signer_id=identity_id, private_key=key)


def _signed_post(client, signer, path, payload):
    headers = signer.sign_headers(payload)
    return client.post(path, json=payload, headers=headers)


class TestAgentRegisterIdentity:
    def test_register_identity(self, client):
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
            "/agent/identities/register-identity",
            json={"identity_id": "agent-1", "role": "provider", "public_key_pem": pem},
        )
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert r.json()["identity_id"] == "agent-1"

    def test_register_identity_duplicate(self, client):
        _register_identity(client, "agent-dup")
        r = client.post(
            "/agent/identities/register-identity",
            json={"identity_id": "agent-dup", "role": "provider"},
        )
        assert r.status_code == 409


class TestAgentSearchProviders:
    def test_search_requires_complete_profiles(self, client):
        _register_identity(client, "worker-1")
        client.post(
            "/onboarding/profile",
            json={
                "provider_id": "worker-1",
                "profile": {
                    "headline": "Runner",
                    "bio": "I run errands in Shanghai",
                    "skills": [{"skill_id": "errand", "proficiency": 0.9}],
                    "city": "Shanghai",
                    "hourly_rate": 40.0,
                    "availability": {"monday": [{"start": "09:00", "end": "17:00"}]},
                },
            },
        )
        r = client.get("/agent/search_providers?skill=errand&city=Shanghai&max_rate=50")
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["results"][0]["provider_id"] == "worker-1"

    def test_search_free_no_signature(self, client):
        r = client.get("/agent/search_providers")
        assert r.status_code == 200


class TestAgentCreateBounty:
    def test_create_requires_signature(self, client):
        r = client.post("/agent/create_bounty", json={"title": "Task", "description": "Do the thing now"})
        assert r.status_code == 401

    def test_create_forbids_unregistered_identity(self, client):
        key = _make_key()
        signer = MessageSigner(signer_id="ghost", private_key=key)
        payload = {"title": "Valid task", "description": "Do the thing correctly now"}
        r = _signed_post(client, signer, "/agent/create_bounty", payload)
        assert r.status_code == 403

    def test_create_uses_signer_as_poster(self, client):
        signer = _register_identity(client, "poster-1")
        payload = {
            "title": "Pick up package",
            "description": "Pick a package from post office and deliver it home",
            "completion_criteria": "package delivered",
            "evidence_types": ["photo"],
            "price": 50.0,
        }
        r = _signed_post(client, signer, "/agent/create_bounty", payload)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["bounty"]["poster_id"] == "poster-1"
        assert body["bounty"]["status"] == "draft"

    def test_create_dry_run(self, client):
        signer = _register_identity(client, "poster-1")
        payload = {
            "title": "Pick up package",
            "description": "Pick a package from post office and deliver it home",
            "completion_criteria": "package delivered",
            "evidence_types": ["photo"],
            "price": 50.0,
            "dry_run": True,
        }
        r = _signed_post(client, signer, "/agent/create_bounty", payload)
        assert r.status_code == 200
        assert r.json()["dry_run"] is True
        assert r.json()["valid"] is True

    def test_create_validation_error(self, client):
        signer = _register_identity(client, "poster-1")
        payload = {"title": "Pick up package", "description": "short", "price": 1.0}
        r = _signed_post(client, signer, "/agent/create_bounty", payload)
        assert r.json()["error"]


class TestAgentBountyLifecycle:
    def test_full_flow_with_signature(self, client):
        poster = _register_identity(client, "poster-1")
        worker = _register_identity(client, "worker-1")
        client.post(
            "/onboarding/profile",
            json={
                "provider_id": "worker-1",
                "profile": {
                    "headline": "Runner",
                    "bio": "I run errands",
                    "skills": [{"skill_id": "errand", "proficiency": 0.9}],
                    "city": "Shanghai",
                    "hourly_rate": 30.0,
                    "availability": {"monday": [{"start": "09:00", "end": "17:00"}]},
                },
            },
        )

        payload = {
            "title": "Pick up package",
            "description": "Pick a package from post office and deliver it home",
            "completion_criteria": "package delivered",
            "evidence_types": ["photo", "link"],
            "price": 50.0,
            "city": "Shanghai",
        }
        r = _signed_post(client, poster, "/agent/create_bounty", payload)
        bounty_id = r.json()["bounty"]["id"]

        r = client.post(f"/market/bounties/{bounty_id}/publish")
        assert r.json()["bounty"]["status"] == "open"

        r = client.post(
            f"/market/bounties/{bounty_id}/apply",
            json={"applicant_id": "worker-1", "message": "I can do this"},
        )
        app_id = r.json()["application"]["id"]

        r = _signed_post(
            client, poster, "/agent/accept_application",
            {"bounty_id": bounty_id, "application_id": app_id},
        )
        assert r.json()["bounty"]["status"] == "assigned"

        r = _signed_post(
            client, worker, "/agent/submit_delivery",
            {"bounty_id": bounty_id, "evidence": {"photo": "url"}},
        )
        assert r.json()["bounty"]["status"] == "submitted"

        r = _signed_post(
            client, poster, "/agent/confirm_delivery",
            {"bounty_id": bounty_id, "accepted": True},
        )
        assert r.json()["bounty"]["status"] == "work_completed"

        r = client.post(f"/market/bounties/{bounty_id}/settle")
        assert r.json()["settlement"]["status"] == "paid"

    def test_accept_requires_signature(self, client):
        r = client.post("/agent/accept_application", json={"bounty_id": "b", "application_id": "a"})
        assert r.status_code == 401


class TestAgentListBounties:
    def test_mine_requires_signature(self, client):
        r = client.get("/agent/list_bounties?mine=true")
        assert r.status_code == 401

    def test_mine_filters_by_signer(self, client):
        signer = _register_identity(client, "poster-1")
        for title in ("Alpha task", "Beta task"):
            payload = {
                "title": title,
                "description": "A sufficiently long task description for validation",
                "completion_criteria": "done",
                "evidence_types": ["text"],
                "price": 30.0,
            }
            _signed_post(client, signer, "/agent/create_bounty", payload)
        r = client.get("/agent/list_bounties?status=draft")
        assert r.json()["total"] == 2
        headers = signer.sign_headers({})
        r = client.get("/agent/list_bounties?status=draft&mine=true", headers=headers)
        assert r.json()["total"] == 2
        assert all(b["poster_id"] == "poster-1" for b in r.json()["bounties"])


class TestAgentBridges:
    def test_heartbeat(self, client):
        signer = _register_identity(client, "poster-1")
        r = _signed_post(client, signer, "/agent/bridges/heartbeat", {"session_id": "bridge-1"})
        assert r.json()["success"] is False

    def test_connect_and_heartbeat(self, client):
        signer = _register_identity(client, "poster-1")
        r = _signed_post(
            client, signer, "/agent/bridges/connect",
            {"session_id": "bridge-1", "remote_url": "https://peer.example.com", "api_key": "k"},
        )
        assert r.json()["success"] is True
        r = _signed_post(client, signer, "/agent/bridges/heartbeat", {"session_id": "bridge-1"})
        assert r.json()["success"] is True


def _make_key():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.generate()
