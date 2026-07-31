"""Tests for Phase C — onboarding / provider / bounty / protocol API endpoints."""

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillos.db.models import IdentityModel
from skillos.market.api import router as market_router
from skillos.protocol.identity_client import IdentityClient
from skillos.web_api.onboarding import router as onboarding_router
from skillos.web_api.protocol import router as protocol_router


def _build_client():
    app = FastAPI()
    app.include_router(market_router)
    app.include_router(onboarding_router)
    app.include_router(protocol_router)
    return TestClient(app)


@pytest.fixture
def client(db_session):
    return _build_client()


def _make_identity(client, identity_id="prov-1", role="provider"):
    """注册一个携带自持 Ed25519 keypair 的身份，返回 (私钥, 响应)。"""
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
        json={"identity_id": identity_id, "role": role, "public_key_pem": pem},
    )
    return key, r


class TestOnboardingRegister:
    def test_register_creates_identity_and_profile(self, client, db_session):
        r = client.post("/onboarding/register", json={"identity_id": "prov-a", "role": "provider"})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["role"] == "provider"
        assert body["profile"]["provider_id"] == "prov-a"
        assert body["profile"]["is_profile_complete"] is False
        assert db_session.query(IdentityModel).filter(IdentityModel.identity_id == "prov-a").count() == 1

    def test_register_supports_both_role(self, client):
        r = client.post("/onboarding/register", json={"identity_id": "prov-b", "role": "both"})
        assert r.status_code == 200
        assert r.json()["role"] == "both"

    def test_register_rejects_invalid_role(self, client):
        r = client.post("/onboarding/register", json={"identity_id": "prov-c", "role": "superadmin"})
        assert r.status_code == 422

    def test_register_duplicate_conflict(self, client):
        client.post("/onboarding/register", json={"identity_id": "prov-d", "role": "provider"})
        r = client.post("/onboarding/register", json={"identity_id": "prov-d", "role": "provider"})
        assert r.status_code == 409

    def test_register_accepts_provided_public_key(self, client):
        key, r = _make_identity(client, identity_id="prov-e", role="provider")
        assert r.status_code == 200
        assert "BEGIN PUBLIC KEY" in r.json()["public_key_pem"]

    def test_register_rejects_invalid_pem(self, client):
        r = client.post(
            "/onboarding/register",
            json={"identity_id": "prov-f", "role": "provider", "public_key_pem": "not-a-key"},
        )
        assert r.status_code == 422


class TestOnboardingVerify:
    def test_verify_success(self, client, db_session):
        ic = IdentityClient()
        ic.register_identity("prov-1", "provider")
        pem = ic.get_identity("prov-1").public_key_pem
        r = client.post(
            "/onboarding/register",
            json={"identity_id": "prov-1", "role": "provider", "public_key_pem": pem},
        )
        assert r.status_code == 200
        challenge = "random-challenge-value"
        sig = ic.sign("prov-1", challenge)
        assert sig is not None
        r = client.post(
            "/onboarding/verify",
            json={"identity_id": "prov-1", "challenge": challenge, "challenge_signature": sig.signature},
        )
        assert r.status_code == 200
        assert r.json()["verified"] is True
        assert r.json()["profile"]["is_verified"] is True
        assert db_session.query(IdentityModel).filter(
            IdentityModel.identity_id == "prov-1"
        ).first().metadata_json["verified"] is True

    def test_verify_invalid_signature(self, client):
        _make_identity(client, identity_id="prov-2")
        r = client.post(
            "/onboarding/verify",
            json={"identity_id": "prov-2", "challenge": "c", "challenge_signature": "aW52YWxpZA=="},
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "invalid_signature"

    def test_verify_unknown_identity(self, client):
        r = client.post(
            "/onboarding/verify",
            json={"identity_id": "nope", "challenge": "c", "challenge_signature": "eA=="},
        )
        assert r.status_code == 404


class TestOnboardingProfile:
    def _complete(self, client):
        client.post("/onboarding/register", json={"identity_id": "prov-x", "role": "provider"})
        r = client.post(
            "/onboarding/profile",
            json={
                "provider_id": "prov-x",
                "profile": {
                    "headline": "Errand Runner",
                    "bio": "Fast and reliable runner in Shanghai",
                    "skills": [{"skill_id": "errand", "proficiency": 0.9, "category": "physical"}],
                    "city": "Shanghai",
                    "country": "CN",
                    "timezone": "Asia/Shanghai",
                    "hourly_rate": 60.0,
                    "currency": "CNY",
                    "availability": {"monday": [{"start": "09:00", "end": "17:00"}]},
                },
            },
        )
        return r

    def test_profile_completes_provider(self, client):
        r = self._complete(client)
        assert r.status_code == 200
        profile = r.json()["profile"]
        assert profile["is_profile_complete"] is True
        assert profile["profile_complete_score"] >= 0.8
        assert profile["city"] == "Shanghai"
        assert profile["hourly_rate"] == 60.0

    def test_completeness_missing_fields(self, client):
        client.post("/onboarding/register", json={"identity_id": "prov-y", "role": "provider"})
        r = client.get("/onboarding/profile/prov-y/completeness")
        assert r.status_code == 200
        body = r.json()
        assert body["is_complete"] is False
        assert set(body["missing_fields"]) == {"headline", "bio", "skills", "city", "hourly_rate", "availability"}

    def test_profile_unknown_provider(self, client):
        r = client.post("/onboarding/profile", json={"provider_id": "nope", "profile": {"headline": "x"}})
        assert r.status_code == 404

    def test_completeness_unknown_provider(self, client):
        r = client.get("/onboarding/profile/nope/completeness")
        assert r.status_code == 404


class TestMarketProviders:
    def test_search_only_complete_profiles(self, client):
        client.post("/onboarding/register", json={"identity_id": "prov-1", "role": "provider"})
        client.post(
            "/onboarding/profile",
            json={
                "provider_id": "prov-1",
                "profile": {
                    "headline": "Runner",
                    "bio": "I run errands in Shanghai",
                    "skills": [{"skill_id": "errand", "proficiency": 0.8}],
                    "city": "Shanghai",
                    "hourly_rate": 40.0,
                    "availability": {"monday": [{"start": "09:00", "end": "17:00"}]},
                },
            },
        )
        r = client.get("/market/providers/search?city=Shanghai")
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["providers"][0]["provider_id"] == "prov-1"

    def test_search_filters_by_max_rate(self, client):
        for pid, rate in [("prov-a", 30.0), ("prov-b", 100.0)]:
            client.post("/onboarding/register", json={"identity_id": pid, "role": "provider"})
            client.post(
                "/onboarding/profile",
                json={
                    "provider_id": pid,
                    "profile": {
                        "headline": "H",
                        "bio": "Available for tasks",
                        "skills": [{"skill_id": "s", "proficiency": 0.8}],
                        "city": "Shanghai",
                        "hourly_rate": rate,
                        "availability": {"monday": [{"start": "09:00", "end": "17:00"}]},
                    },
                },
            )
        r = client.get("/market/providers/search?city=Shanghai&max_rate=50")
        assert r.json()["total"] == 1
        assert r.json()["providers"][0]["provider_id"] == "prov-a"

    def test_search_filters_by_category(self, client):
        client.post("/onboarding/register", json={"identity_id": "prov-c1", "role": "provider"})
        client.post(
            "/onboarding/profile",
            json={
                "provider_id": "prov-c1",
                "profile": {
                    "headline": "Photographer",
                    "bio": "Event photography",
                    "skills": [{"skill_id": "photo", "proficiency": 0.9}],
                    "categories": ["photography"],
                    "city": "Shanghai",
                    "hourly_rate": 80.0,
                    "availability": {"monday": [{"start": "09:00", "end": "17:00"}]},
                },
            },
        )
        r = client.get("/market/providers/search?category=photography")
        assert r.status_code == 200
        assert r.json()["total"] == 1
        r = client.get("/market/providers/search?category=delivery")
        assert r.json()["total"] == 0

    def test_profile_invalid_fields_rejected(self, client):
        client.post("/onboarding/register", json={"identity_id": "prov-z", "role": "provider"})
        r = client.post(
            "/onboarding/profile",
            json={"provider_id": "prov-z", "profile": {"hourly_rate": "not-a-number"}},
        )
        assert r.status_code == 422

    def test_public_profile_omits_sensitive_fields(self, client):
        client.post("/onboarding/register", json={"identity_id": "prov-1", "role": "provider"})
        client.post(
            "/onboarding/profile",
            json={"provider_id": "prov-1", "profile": {"phone": "13800000000", "gender": "other"}},
        )
        r = client.get("/market/providers/prov-1")
        assert r.status_code == 200
        assert "phone" not in r.json()
        assert "gender" not in r.json()
        assert "public_key" not in r.json()

    def test_public_profile_unknown(self, client):
        r = client.get("/market/providers/nope")
        assert r.json()["error"] == "Provider not found"


class TestMarketBounties:
    def test_dry_run_preview(self, client):
        r = client.post(
            "/market/bounties",
            json={
                "poster_id": "prov-1",
                "title": "Pick up package",
                "description": "Pick a package from post office and deliver it home",
                "completion_criteria": "package delivered",
                "evidence_types": ["photo"],
                "price": 30.0,
                "dry_run": True,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["dry_run"] is True
        assert body["valid"] is True

    def test_dry_run_invalid(self, client):
        payload = {
            "poster_id": "prov-1",
            "title": "Pick up package",
            "description": "short",
            "price": 1.0,
            "dry_run": True,
        }
        r = client.post("/market/bounties", json=payload)
        assert r.json()["error"]

    def test_create_missing_poster_id_returns_error(self, client):
        payload = {
            "title": "Valid task",
            "description": "dddddddddd",
            "completion_criteria": "x",
            "evidence_types": ["text"],
            "price": 10.0,
        }
        r = client.post("/market/bounties", json=payload)
        assert r.status_code == 200
        assert "error" in r.json()

    def test_full_bounty_lifecycle(self, client, db_session):
        for pid, role in [("poster", "consumer"), ("worker", "provider")]:
            client.post("/onboarding/register", json={"identity_id": pid, "role": role})
        client.post(
            "/onboarding/profile",
            json={
                "provider_id": "worker",
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

        r = client.post(
            "/market/bounties",
            json={
                "poster_id": "poster",
                "title": "Pick up package",
                "description": "Pick a package from post office and deliver it home",
                "completion_criteria": "package delivered",
                "evidence_types": ["photo", "link"],
                "price": 50.0,
                "city": "Shanghai",
            },
        )
        assert r.status_code == 200
        bounty_id = r.json()["bounty"]["id"]

        r = client.post(f"/market/bounties/{bounty_id}/publish")
        assert r.json()["bounty"]["status"] == "open"

        r = client.post(
            f"/market/bounties/{bounty_id}/apply",
            json={"applicant_id": "worker", "message": "I can do this"},
        )
        assert r.json()["success"] is True
        app_id = r.json()["application"]["id"]

        r = client.post(f"/market/bounties/{bounty_id}/applications/{app_id}/accept")
        assert r.json()["bounty"]["status"] == "assigned"

        r = client.post(f"/market/bounties/{bounty_id}/submit", json={"evidence": {"photo": "url"}})
        assert r.json()["bounty"]["status"] == "submitted"

        r = client.post(f"/market/bounties/{bounty_id}/confirm", json={"accepted": True})
        assert r.json()["bounty"]["status"] == "work_completed"

        r = client.post(f"/market/bounties/{bounty_id}/settle")
        assert r.json()["settlement"]["status"] == "paid"
        assert r.json()["settlement"]["total_amount"] == 50.0

        r = client.get(f"/market/bounties/{bounty_id}/settlements")
        assert r.json()["bounty_id"] == bounty_id
        assert len(r.json()["settlements"]) == 1
        assert r.json()["settlements"][0]["total_amount"] == 50.0

    def test_apply_validation_error(self, client):
        r = client.post("/market/bounties/bty-nope/apply", json={"applicant_id": "worker"})
        assert r.json()["error"]


class TestProtocolEndpoints:
    def test_identities_returns_registered(self, client):
        client.post("/onboarding/register", json={"identity_id": "prov-1", "role": "provider"})
        client.post("/onboarding/register", json={"identity_id": "consumer-1", "role": "consumer"})
        r = client.get("/protocol/identities")
        assert r.json()["total"] == 2
        fields = {i["identity_id"]: i for i in r.json()["identities"]}
        assert fields["prov-1"]["role"] == "provider"
        assert fields["prov-1"]["verified"] is False
        assert "public_key" not in fields["prov-1"]

    def test_identities_filter_by_role(self, client):
        client.post("/onboarding/register", json={"identity_id": "prov-1", "role": "provider"})
        client.post("/onboarding/register", json={"identity_id": "consumer-1", "role": "consumer"})
        r = client.get("/protocol/identities?role=provider")
        assert r.json()["total"] == 1
        assert r.json()["identities"][0]["identity_id"] == "prov-1"

    def test_registry_search_delegates(self, client):
        client.post("/onboarding/register", json={"identity_id": "prov-1", "role": "provider"})
        client.post(
            "/onboarding/profile",
            json={
                "provider_id": "prov-1",
                "profile": {
                    "headline": "Errand Runner",
                    "bio": "I run errands in Shanghai",
                    "skills": [{"skill_id": "errand", "proficiency": 0.9}],
                    "city": "Shanghai",
                    "hourly_rate": 45.0,
                    "availability": {"monday": [{"start": "09:00", "end": "17:00"}]},
                },
            },
        )
        r = client.get("/protocol/registry/search?query=Shanghai")
        assert r.json()["total"] == 1
        assert r.json()["results"][0]["provider_id"] == "prov-1"

    def test_protocol_providers_endpoint(self, client):
        client.post("/onboarding/register", json={"identity_id": "prov-1", "role": "provider"})
        client.post(
            "/onboarding/profile",
            json={
                "provider_id": "prov-1",
                "profile": {
                    "headline": "H",
                    "bio": "Available",
                    "skills": [{"skill_id": "s", "proficiency": 0.8}],
                    "city": "Beijing",
                    "hourly_rate": 30.0,
                    "availability": {"monday": [{"start": "09:00", "end": "17:00"}]},
                },
            },
        )
        r = client.get("/protocol/providers?city=Beijing")
        assert r.json()["total"] == 1
        assert r.json()["providers"][0]["provider_id"] == "prov-1"
