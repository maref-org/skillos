"""Tests for negmarket.api — FastAPI REST adapter (optional)"""
import pytest


pytest.importorskip("fastapi")


from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillos.negmarket.models import AntiPatternSkill, NegativeSample

from negmarket.api import (
    get_storage as _orig_get_storage,
    get_pipeline as _orig_get_pipeline,
    get_generator as _orig_get_generator,
    router,
)

import negmarket.api as _api_mod

LONG_TEXT = "error " * 16000  # 96000 chars, within 100000 max_length


@pytest.fixture
def sample():
    return NegativeSample(id="sample-001", contributor_id="user-1", category="api_error", risk_level="high")


@pytest.fixture
def skill():
    return AntiPatternSkill(
        id="skill-001",
        sample_id="sample-001",
        generated_by="user-1",
        skill_manifest={
            "name": "api_error_check",
            "description": "Detect API errors",
            "metadata": {"risk_level": "high", "category": "api_error"},
            "price_per_call": 0.1,
        },
    )


def _build_client(overrides: dict | None = None):
    app = FastAPI()
    app.include_router(router)
    if overrides:
        app.dependency_overrides.update(overrides)
    return TestClient(app)


class TestUploadEndpoint:
    def test_upload_success(self, sample, skill):
        mock_storage = MagicMock()
        mock_pipeline = MagicMock()
        mock_pipeline.process.return_value = sample
        mock_gen = MagicMock()
        mock_gen.generate.return_value = skill

        overrides = {
            _orig_get_storage: lambda: mock_storage,
            _orig_get_pipeline: lambda: mock_pipeline,
        }

        _orig_apg = _api_mod.AntiPatternGenerator
        _api_mod.AntiPatternGenerator = lambda: mock_gen

        client = _build_client(overrides)
        resp = client.post(
            "/negmarket/upload",
            json={
                "raw_text": "sensitive data here",
                "category": "api_error",
                "contributor_id": "user-1",
                "contributor_secret": "my-secret-key",
            },
        )

        _api_mod.AntiPatternGenerator = _orig_apg

        assert resp.status_code == 200
        data = resp.json()
        assert data["sample_id"] == "sample-001"
        assert data["risk_level"] == "high"
        assert data["anti_pattern_skill_id"] == "skill-001"
        mock_storage.save_sample.assert_called_once()
        mock_storage.save_anti_pattern.assert_called_once()

    def test_upload_missing_contributor_id(self):
        client = _build_client()
        resp = client.post(
            "/negmarket/upload",
            json={"raw_text": "some text"},
        )
        assert resp.status_code == 422

    def test_upload_empty_text(self):
        client = _build_client()
        resp = client.post(
            "/negmarket/upload",
            json={
                "raw_text": "",
                "category": "general",
                "contributor_id": "user-1",
                "contributor_secret": "key",
            },
        )
        assert resp.status_code == 422


class TestCallEndpoint:
    def test_call_existing_sample(self, sample, skill):
        mock_storage = MagicMock()
        mock_storage.get_sample.return_value = sample
        mock_storage.get_anti_pattern.return_value = skill
        mock_gen = MagicMock()
        mock_gen.call.return_value = MagicMock(
            risk_level="low",
            warning="Pattern matched",
            anti_pattern_id="skill-001",
        )

        overrides = {
            _orig_get_storage: lambda: mock_storage,
            _orig_get_generator: lambda: mock_gen,
        }
        client = _build_client(overrides)
        resp = client.post(
            "/negmarket/sample-001/call",
            json={"input": "test data"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_level"] == "low"
        assert data["warning"] == "Pattern matched"
        assert data["anti_pattern_id"] == "skill-001"
        mock_storage.update_call_stats.assert_called_once_with("skill-001")

    def test_call_nonexistent_sample(self):
        mock_storage = MagicMock()
        mock_storage.get_sample.return_value = None

        overrides = {
            _orig_get_storage: lambda: mock_storage,
            _orig_get_generator: lambda: MagicMock(),
        }
        client = _build_client(overrides)

        resp = client.post("/negmarket/nonexistent/call", json={})
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


class TestDiscoverEndpoint:
    def test_discover_all(self):
        skills = [
            AntiPatternSkill(
                id="s1", sample_id="sp1", generated_by="u1",
                skill_manifest={
                    "name": "Skill A", "description": "Desc A",
                    "metadata": {"risk_level": "high", "category": "api_error"},
                    "price_per_call": 0.2,
                },
                call_count=5,
            ),
            AntiPatternSkill(
                id="s2", sample_id="sp2", generated_by="u2",
                skill_manifest={
                    "name": "Skill B", "description": "Desc B",
                    "metadata": {"risk_level": "low", "category": "security"},
                    "price_per_call": 0.15,
                },
                call_count=3,
            ),
        ]

        mock_storage = MagicMock()
        mock_storage.discover_anti_patterns.return_value = skills

        overrides = {_orig_get_storage: lambda: mock_storage}
        client = _build_client(overrides)
        resp = client.get("/negmarket/discover")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["skills"]) == 2
        assert data["skills"][0]["name"] == "Skill A"
        assert data["skills"][1]["name"] == "Skill B"

    def test_discover_filter_category(self):
        skill = AntiPatternSkill(
            id="s1", sample_id="sp1", generated_by="u1",
            skill_manifest={
                "name": "Security Skill", "description": "",
                "metadata": {"risk_level": "high", "category": "security"},
                "price_per_call": 0.1,
            },
            call_count=1,
        )

        mock_storage = MagicMock()
        mock_storage.discover_anti_patterns.return_value = [skill]

        overrides = {_orig_get_storage: lambda: mock_storage}
        client = _build_client(overrides)
        resp = client.get("/negmarket/discover?category=security")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["skills"][0]["category"] == "security"
        mock_storage.discover_anti_patterns.assert_called_once_with("security", None)

    def test_discover_empty(self):
        mock_storage = MagicMock()
        mock_storage.discover_anti_patterns.return_value = []

        overrides = {_orig_get_storage: lambda: mock_storage}
        client = _build_client(overrides)
        resp = client.get("/negmarket/discover")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["skills"] == []


@pytest.fixture
def client(tmp_path, db_path=None):
    _db_path = db_path or str(tmp_path / "test_negmarket.db")

    def get_test_storage():
        from negmarket.storage import SQLiteNegMarketStorage
        return SQLiteNegMarketStorage(_db_path)

    overrides = {_orig_get_storage: get_test_storage}
    return _build_client(overrides)


class TestUploadEndpointIntegration:
    def test_upload_success(self, client):
        resp = client.post("/negmarket/upload", json={
            "raw_text": "API call failed with timeout after 30s on user-123 login",
            "category": "api_error",
            "contributor_id": "user-1",
            "contributor_secret": "secret-1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "sample_id" in data
        assert "risk_level" in data
        assert "anti_pattern_skill_id" in data
        assert data["risk_level"] == "medium"

    def test_upload_empty_text_rejected(self, client):
        resp = client.post("/negmarket/upload", json={
            "raw_text": "",
            "category": "general",
            "contributor_id": "user-1",
            "contributor_secret": "secret-1",
        })
        assert resp.status_code == 422

    def test_upload_high_risk_content(self, client):
        resp = client.post("/negmarket/upload", json={
            "raw_text": "Security breach: API key exposed in git commit containing sk-123456789012345678901234",
            "category": "security",
            "contributor_id": "user-2",
            "contributor_secret": "secret-2",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_level"] == "high"

    def test_upload_long_text(self, client):
        resp = client.post("/negmarket/upload", json={
            "raw_text": LONG_TEXT,
            "category": "general",
            "contributor_id": "user-1",
            "contributor_secret": "secret-1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "sample_id" in data
        assert "anti_pattern_skill_id" in data


class TestCallEndpointIntegration:
    def test_call_existing_anti_pattern(self, client):
        upload = client.post("/negmarket/upload", json={
            "raw_text": "Database connection pool exhausted after 100 concurrent requests",
            "category": "database",
            "contributor_id": "user-1",
            "contributor_secret": "secret-1",
        })
        sample_id = upload.json()["sample_id"]

        resp = client.post(f"/negmarket/{sample_id}/call", json={"params": {}})
        assert resp.status_code == 200
        data = resp.json()
        assert "risk_level" in data
        assert "warning" in data
        assert "anti_pattern_id" in data

    def test_call_nonexistent_sample(self, client):
        resp = client.post("/negmarket/nonexistent-id/call", json={"params": {}})
        assert resp.status_code == 404

    def test_call_tracks_incrementing_stats(self, client):
        upload = client.post("/negmarket/upload", json={
            "raw_text": "Memory leak in cache layer after 1M entries",
            "category": "performance",
            "contributor_id": "user-3",
            "contributor_secret": "secret-3",
        })
        sample_id = upload.json()["sample_id"]
        skill_id = upload.json()["anti_pattern_skill_id"]

        for _ in range(3):
            resp = client.post(f"/negmarket/{sample_id}/call", json={})
            assert resp.status_code == 200
            assert resp.json()["anti_pattern_id"] == skill_id

        resp = client.get("/negmarket/discover")
        skills = resp.json()["skills"]
        matched = [s for s in skills if s["id"] == skill_id]
        assert len(matched) == 1
        assert matched[0]["call_count"] >= 3


class TestDiscoverEndpointIntegration:
    def test_discover_all(self, client):
        client.post("/negmarket/upload", json={
            "raw_text": "Rate limit exceeded for API endpoint /v1/users",
            "category": "api_error",
            "contributor_id": "user-1",
            "contributor_secret": "secret-1",
        })
        client.post("/negmarket/upload", json={
            "raw_text": "SSL certificate expired on prod.example.com",
            "category": "security",
            "contributor_id": "user-2",
            "contributor_secret": "secret-2",
        })

        resp = client.get("/negmarket/discover")
        assert resp.status_code == 200
        data = resp.json()
        assert "skills" in data
        assert "total" in data
        assert data["total"] >= 2

    def test_discover_filter_by_category(self, client):
        client.post("/negmarket/upload", json={
            "raw_text": "Timeout while connecting to database cluster",
            "category": "database",
            "contributor_id": "user-1",
            "contributor_secret": "secret-1",
        })

        resp = client.get("/negmarket/discover?category=database")
        assert resp.status_code == 200
        data = resp.json()
        for s in data["skills"]:
            assert s["category"] == "database"

    def test_discover_filter_by_risk_level(self, client):
        client.post("/negmarket/upload", json={
            "raw_text": "Critical: API key sk-abcdef1234567890abcdef1234567890 leaked in transaction log",
            "category": "security",
            "contributor_id": "user-3",
            "contributor_secret": "secret-3",
        })

        resp = client.get("/negmarket/discover?risk_level=high")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for s in data["skills"]:
            assert s["risk_level"] == "high"

    def test_discover_empty_when_no_data(self, client):
        resp = client.get("/negmarket/discover?category=nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
