"""Tests for skillos.protocol.registry_client - Skill registry with mocked requests"""

import time
from unittest.mock import MagicMock, patch

from skillos._types import SkillManifest, SkillStatus
from skillos.protocol.registry_client import RegistryClient, RegistryConfig, SearchResult


class TestRegistryConfig:
    def test_defaults(self):
        config = RegistryConfig()
        assert config.base_url == "https://localhost:8080"
        assert config.timeout == 10.0
        assert config.cache_ttl == 300.0

    def test_custom_values(self):
        config = RegistryConfig(
            base_url="https://example.com",
            timeout=30.0,
            cache_ttl=600.0,
        )
        assert config.base_url == "https://example.com"
        assert config.timeout == 30.0
        assert config.cache_ttl == 600.0


class TestSearchResult:
    def test_basic_fields(self):
        result = SearchResult(
            skills=[],
            total=0,
            page=1,
            per_page=20,
        )
        assert result.skills == []
        assert result.total == 0

    def test_with_skills(self):
        skill = SkillManifest(id="s-1", name="Test", version="1.0.0", author="me", description="d")
        result = SearchResult(skills=[skill], total=1, page=2, per_page=10)
        assert len(result.skills) == 1
        assert result.page == 2


class TestRegistryClientInit:
    def test_default_init(self):
        client = RegistryClient()
        assert client.config.base_url == "https://localhost:8080"
        assert client._cache == {}

    def test_custom_config(self):
        config = RegistryConfig(base_url="https://custom", cache_ttl=100.0)
        client = RegistryClient(config=config)
        assert client.config.base_url == "https://custom"
        assert client.config.cache_ttl == 100.0


class TestRegistryClientRegister:
    @patch("skillos.protocol.registry_client.requests.request")
    def test_register_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {"id": "skill-001"}}
        mock_post.return_value = mock_resp

        client = RegistryClient()
        manifest = SkillManifest(
            id="skill-001",
            name="Test Skill",
            version="1.0.0",
            author="tester",
            description="A test",
        )

        result = client.register(manifest)
        assert result == "skill-001"

    @patch("skillos.protocol.registry_client.requests.request")
    def test_register_fallback_on_error(self, mock_post):
        import requests as req_lib

        mock_post.side_effect = req_lib.RequestException("Network error")

        client = RegistryClient()
        manifest = SkillManifest(
            id="fallback-skill",
            name="Fallback",
            version="0.1.0",
            author="tester",
            description="Fallback test",
        )

        result = client.register(manifest)
        assert result == "fallback-skill"

    @patch("skillos.protocol.registry_client.requests.request")
    def test_register_sends_correct_payload(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {"id": "skill-001"}}
        mock_post.return_value = mock_resp

        client = RegistryClient()
        manifest = SkillManifest(
            id="skill-001",
            name="Send Test",
            version="2.0.0",
            author="alice",
            description="desc",
            price_per_call=0.1,
        )

        client.register(manifest)

        _, kwargs = mock_post.call_args
        params = kwargs["json"]["params"]
        assert params["id"] == "skill-001"
        assert params["name"] == "Send Test"
        assert params["version"] == "2.0.0"
        assert params["author"] == "alice"
        assert params["price_per_call"] == 0.1

    @patch("skillos.protocol.registry_client.requests.request")
    @patch.dict("os.environ", {"SKILLOS_API_KEY": "secret-key"})
    def test_register_with_auth(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {"id": "skill-001"}}
        mock_post.return_value = mock_resp

        client = RegistryClient()
        manifest = SkillManifest(
            id="skill-001",
            name="Auth Test",
            version="1.0.0",
            author="tester",
            description="desc",
        )

        client.register(manifest)

        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer secret-key"

    @patch("skillos.protocol.registry_client.requests.request")
    def test_register_caches_on_error(self, mock_post):
        import requests as req_lib

        mock_post.side_effect = req_lib.RequestException("Error")

        client = RegistryClient()
        manifest = SkillManifest(
            id="cached-skill",
            name="Cached",
            version="1.0.0",
            author="tester",
            description="desc",
        )

        client.register(manifest)

        cached = client.get_skill("cached-skill")
        assert cached is not None
        assert cached.name == "Cached"


class TestRegistryClientGetSkill:
    def _make_skill_response_json(self, skill_id="skill-001", name="Test"):
        return {
            "id": skill_id,
            "name": name,
            "version": "1.0.0",
            "author": "author",
            "description": "desc",
            "status": "published",
            "price_per_call": 0.05,
        }

    @patch("skillos.protocol.registry_client.requests.request")
    def test_get_skill_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self._make_skill_response_json()
        mock_get.return_value = mock_resp

        client = RegistryClient()
        result = client.get_skill("skill-001")

        assert result is not None
        assert result.id == "skill-001"
        assert result.name == "Test"

    @patch("skillos.protocol.registry_client.requests.request")
    def test_get_skill_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        client = RegistryClient()
        result = client.get_skill("nonexistent")

        assert result is None

    @patch("skillos.protocol.registry_client.requests.request")
    def test_get_skill_network_error(self, mock_get):
        import requests as req_lib

        mock_get.side_effect = req_lib.RequestException("Timeout")

        client = RegistryClient()
        result = client.get_skill("skill-001")

        assert result is None

    @patch("skillos.protocol.registry_client.requests.request")
    def test_get_skill_cache_hit(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self._make_skill_response_json()
        mock_get.return_value = mock_resp

        client = RegistryClient()
        client.get_skill("skill-001")

        mock_get.reset_mock()

        cached = client.get_skill("skill-001")
        assert cached is not None
        mock_get.assert_not_called()

    @patch("skillos.protocol.registry_client.requests.request")
    def test_get_skill_cache_expired(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self._make_skill_response_json()
        mock_get.return_value = mock_resp

        config = RegistryConfig(cache_ttl=0.001)
        client = RegistryClient(config=config)
        client.get_skill("skill-001")

        time.sleep(0.01)

        mock_get.reset_mock()
        mock_resp2 = MagicMock()
        mock_resp2.status_code = 200
        mock_resp2.json.return_value = self._make_skill_response_json()
        mock_get.return_value = mock_resp2

        client.get_skill("skill-001")
        mock_get.assert_called_once()

    @patch("skillos.protocol.registry_client.requests.request")
    def test_get_skill_with_version(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self._make_skill_response_json()
        mock_get.return_value = mock_resp

        client = RegistryClient()
        client.get_skill("skill-001", version="2.0.0")

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["version"] == "2.0.0"

    @patch("skillos.protocol.registry_client.requests.request")
    def test_get_skill_different_cache_keys_for_versions(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self._make_skill_response_json()
        mock_get.return_value = mock_resp

        client = RegistryClient()
        client.get_skill("skill-001")
        client.get_skill("skill-001", version="2.0.0")

        assert len(client._cache) == 2


class TestRegistryClientSearch:
    def _make_search_response(self, items=None, total=0, page=1, per_page=20):
        return {
            "items": items or [],
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    @patch("skillos.protocol.registry_client.requests.request")
    def test_search_success(self, mock_get):
        items = [
            {
                "id": "s-1",
                "name": "Skill A",
                "version": "1.0.0",
                "author": "alice",
                "description": "d",
                "status": "published",
            },
            {
                "id": "s-2",
                "name": "Skill B",
                "version": "1.0.0",
                "author": "bob",
                "description": "d",
                "status": "published",
            },
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self._make_search_response(items=items, total=2)
        mock_get.return_value = mock_resp

        client = RegistryClient()
        result = client.search("test")

        assert result.total == 2
        assert len(result.skills) == 2

    @patch("skillos.protocol.registry_client.requests.request")
    def test_search_with_filters(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self._make_search_response()
        mock_get.return_value = mock_resp

        client = RegistryClient()
        client.search("python", author="alice", status=SkillStatus.PUBLISHED, page=2, per_page=50)

        _, kwargs = mock_get.call_args
        params = kwargs["params"]
        assert params["q"] == "python"
        assert params["author"] == "alice"
        assert params["status"] == "published"
        assert params["page"] == 2
        assert params["per_page"] == 50

    @patch("skillos.protocol.registry_client.requests.request")
    def test_search_network_error(self, mock_get):
        import requests as req_lib

        mock_get.side_effect = req_lib.RequestException("Error")

        client = RegistryClient()
        result = client.search("test")

        assert result.skills == []
        assert result.total == 0
        assert result.page == 1

    @patch("skillos.protocol.registry_client.requests.request")
    @patch.dict("os.environ", {"SKILLOS_API_KEY": "key-123"})
    def test_search_with_auth(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self._make_search_response()
        mock_get.return_value = mock_resp

        client = RegistryClient()
        client.search("test")

        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer key-123"


class TestRegistryClientPublish:
    @patch("skillos.protocol.registry_client.requests.request")
    def test_publish_success(self, mock_post):
        mock_resp = MagicMock()
        mock_post.return_value = mock_resp

        client = RegistryClient()
        result = client.publish("skill-001", "1.0.0")

        assert result is True

    @patch("skillos.protocol.registry_client.requests.request")
    def test_publish_failure(self, mock_post):
        import requests as req_lib

        mock_post.side_effect = req_lib.RequestException("Error")

        client = RegistryClient()
        result = client.publish("skill-001", "1.0.0")

        assert result is False

    @patch("skillos.protocol.registry_client.requests.request")
    def test_publish_sends_correct_method(self, mock_post):
        mock_resp = MagicMock()
        mock_post.return_value = mock_resp

        client = RegistryClient()
        client.publish("skill-xyz", "2.5.0")

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["method"] == "skill.publish"
        assert kwargs["json"]["params"]["id"] == "skill-xyz"
        assert kwargs["json"]["params"]["version"] == "2.5.0"


class TestRegistryClientDeprecate:
    @patch("skillos.protocol.registry_client.requests.request")
    def test_deprecate_success(self, mock_post):
        mock_resp = MagicMock()
        mock_post.return_value = mock_resp

        client = RegistryClient()
        result = client.deprecate("skill-001", "Replaced by v2")

        assert result is True

    @patch("skillos.protocol.registry_client.requests.request")
    def test_deprecate_failure(self, mock_post):
        import requests as req_lib

        mock_post.side_effect = req_lib.RequestException("Error")

        client = RegistryClient()
        result = client.deprecate("skill-001")

        assert result is False

    @patch("skillos.protocol.registry_client.requests.request")
    def test_deprecate_default_reason(self, mock_post):
        mock_resp = MagicMock()
        mock_post.return_value = mock_resp

        client = RegistryClient()
        client.deprecate("skill-001")

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["params"]["reason"] == ""


class TestRegistryClientGetCallStats:
    @patch("skillos.protocol.registry_client.requests.request")
    def test_get_stats_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"total_calls": 1000, "total_revenue": 50.0}
        mock_get.return_value = mock_resp

        client = RegistryClient()
        stats = client.get_call_stats("skill-001")

        assert stats["total_calls"] == 1000
        assert stats["total_revenue"] == 50.0

    @patch("skillos.protocol.registry_client.requests.request")
    def test_get_stats_network_error(self, mock_get):
        import requests as req_lib

        mock_get.side_effect = req_lib.RequestException("Error")

        client = RegistryClient()
        stats = client.get_call_stats("skill-001")

        assert stats["total_calls"] == 0
        assert stats["total_revenue"] == 0.0


class TestRegistryClientInvalidateCache:
    def test_invalidate_all(self):
        client = RegistryClient()
        client._cache["skill-001"] = (MagicMock(), time.time())
        client._cache["skill-002"] = (MagicMock(), time.time())

        client.invalidate_cache()

        assert len(client._cache) == 0

    def test_invalidate_specific(self):
        client = RegistryClient()
        client._cache["skill-001"] = (MagicMock(), time.time())
        client._cache["skill-001:v2"] = (MagicMock(), time.time())
        client._cache["other-001"] = (MagicMock(), time.time())

        client.invalidate_cache("skill-001")

        assert "skill-001" not in client._cache
        assert "skill-001:v2" not in client._cache
        assert "other-001" in client._cache


class TestRegistryClientParseManifest:
    def test_parse_full_data(self):
        data = {
            "id": "skill-001",
            "name": "Test Skill",
            "version": "2.0.0",
            "author": "alice",
            "description": "desc",
            "license": "MIT",
            "status": "published",
            "entry_point": "main.py",
            "dependencies": ["numpy", "pandas"],
            "price_per_call": 0.1,
            "metadata": {"category": "ai"},
            "created_at": 1000000.0,
        }

        manifest = RegistryClient._parse_manifest(data)

        assert manifest.id == "skill-001"
        assert manifest.name == "Test Skill"
        assert manifest.version == "2.0.0"
        assert manifest.author == "alice"
        assert manifest.license_type == "MIT"
        assert manifest.status == SkillStatus.PUBLISHED
        assert manifest.entry_point == "main.py"
        assert manifest.dependencies == ["numpy", "pandas"]
        assert manifest.price_per_call == 0.1
        assert manifest.metadata == {"category": "ai"}
        assert manifest.created_at == 1000000.0

    def test_parse_minimal_data(self):
        data = {"id": "minimal", "name": "Minimal", "author": "anon", "description": ""}

        manifest = RegistryClient._parse_manifest(data)

        assert manifest.id == "minimal"
        assert manifest.version == "1.0.0"
        assert manifest.license_type == "AGPL-3.0"
        assert manifest.status == SkillStatus.DRAFT
        assert manifest.entry_point is None
        assert manifest.dependencies == []
        assert manifest.price_per_call == 0.0
        assert manifest.metadata == {}
