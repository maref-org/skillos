"""Tests for skillos.protocol.matcher_client - Intent-skill matching engine"""

from unittest.mock import MagicMock, patch

from skillos.protocol.matcher_client import (
    MatchCandidate,
    MatcherClient,
    MatchRequest,
    MatchResult,
)


class TestMatchRequest:
    def test_basic_fields(self):
        req = MatchRequest(
            user_intent="search for Python tutorials",
            user_id="user-001",
        )
        assert req.user_intent == "search for Python tutorials"
        assert req.user_id == "user-001"

    def test_default_values(self):
        req = MatchRequest(
            user_intent="hello",
            user_id="user-001",
        )
        assert req.context == {}
        assert req.max_results == 5
        assert req.budget_limit_usd is None

    def test_custom_values(self):
        req = MatchRequest(
            user_intent="hello",
            user_id="user-001",
            context={"language": "en"},
            max_results=10,
            budget_limit_usd=1.5,
        )
        assert req.context == {"language": "en"}
        assert req.max_results == 10
        assert req.budget_limit_usd == 1.5


class TestMatchCandidate:
    def test_basic_fields(self):
        candidate = MatchCandidate(
            skill_id="skill-001",
            skill_name="Python Search",
            score=0.95,
            price_per_call=0.05,
            avg_latency_ms=120.0,
            success_rate=0.98,
            author="alice",
        )
        assert candidate.skill_id == "skill-001"
        assert candidate.score == 0.95
        assert candidate.author == "alice"


class TestMatchResult:
    def test_basic_fields(self):
        result = MatchResult(
            request_id="1",
            candidates=[],
            best_match=None,
            match_time_ms=50.0,
            total_available=0,
        )
        assert result.request_id == "1"
        assert result.best_match is None


class TestMatcherClientInit:
    def test_default_init(self):
        client = MatcherClient()
        assert client.base_url == "https://localhost:8080"
        assert client._api_key is None
        assert client._match_history == []

    def test_custom_init(self):
        client = MatcherClient(base_url="https://example.com", api_key="api-key-123")
        assert client.base_url == "https://example.com"
        assert client._api_key == "api-key-123"


class TestMatcherClientAuthHeaders:
    def test_headers_without_api_key(self):
        client = MatcherClient()
        headers = client._auth_headers()

        assert headers == {"Content-Type": "application/json"}
        assert "Authorization" not in headers

    def test_headers_with_api_key(self):
        client = MatcherClient(api_key="secret-key")
        headers = client._auth_headers()

        assert headers["Authorization"] == "Bearer secret-key"
        assert headers["Content-Type"] == "application/json"


class TestMatcherClientMatch:
    def _make_mock_response(self, candidates_data, total_available=5, request_id=1):
        return MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "id": request_id,
                    "result": {
                        "candidates": candidates_data,
                        "total_available": total_available,
                    },
                }
            ),
        )

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_match_success(self, mock_request):
        mock_resp = self._make_mock_response([
            {"skill_id": "skill-001", "skill_name": "Test Skill", "score": 0.95},
        ])
        mock_request.return_value = mock_resp

        client = MatcherClient()
        request = MatchRequest(user_intent="test", user_id="user-001")
        result = client.match(request)

        assert len(result.candidates) == 1
        assert result.candidates[0].skill_id == "skill-001"
        assert result.candidates[0].score == 0.95

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_match_with_multiple_candidates(self, mock_request):
        mock_resp = self._make_mock_response([
            {"skill_id": "skill-001", "skill_name": "Best", "score": 0.95},
            {"skill_id": "skill-002", "skill_name": "Second", "score": 0.80},
            {"skill_id": "skill-003", "skill_name": "Third", "score": 0.60},
        ])
        mock_request.return_value = mock_resp

        client = MatcherClient()
        request = MatchRequest(user_intent="test", user_id="user-001")
        result = client.match(request)

        assert len(result.candidates) == 3
        assert result.total_available == 5

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_match_best_candidate_is_first(self, mock_request):
        mock_resp = self._make_mock_response([
            {"skill_id": "skill-002", "skill_name": "Second", "score": 0.80},
            {"skill_id": "skill-001", "skill_name": "First", "score": 0.95},
        ])
        mock_request.return_value = mock_resp

        client = MatcherClient()
        request = MatchRequest(user_intent="test", user_id="user-001")
        result = client.match(request)

        assert result.best_match is not None
        assert result.best_match.skill_id == "skill-002"

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_match_no_candidates(self, mock_request):
        mock_resp = self._make_mock_response([])
        mock_request.return_value = mock_resp

        client = MatcherClient()
        request = MatchRequest(user_intent="test", user_id="user-001")
        result = client.match(request)

        assert result.candidates == []
        assert result.best_match is None

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_match_candidate_defaults(self, mock_request):
        mock_resp = self._make_mock_response([
            {"skill_id": "skill-001", "skill_name": "Minimal", "score": 0.9},
        ])
        mock_request.return_value = mock_resp

        client = MatcherClient()
        request = MatchRequest(user_intent="test", user_id="user-001")
        result = client.match(request)

        c = result.candidates[0]
        assert c.price_per_call == 0.0
        assert c.avg_latency_ms == 500.0
        assert c.success_rate == 1.0
        assert c.author == "anonymous"

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_match_sends_correct_payload(self, mock_request):
        mock_resp = self._make_mock_response([])
        mock_request.return_value = mock_resp

        client = MatcherClient()
        request = MatchRequest(
            user_intent="find skill",
            user_id="user-123",
            context={"lang": "en"},
            max_results=10,
            budget_limit_usd=2.0,
        )
        client.match(request)

        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert kwargs["json"]["params"]["user_intent"] == "find skill"
        assert kwargs["json"]["params"]["user_id"] == "user-123"
        assert kwargs["json"]["params"]["context"] == {"lang": "en"}
        assert kwargs["json"]["params"]["max_results"] == 10
        assert kwargs["json"]["params"]["budget_limit"] == 2.0

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_match_with_auth_headers(self, mock_request):
        mock_resp = self._make_mock_response([])
        mock_request.return_value = mock_resp

        client = MatcherClient(api_key="my-key")
        request = MatchRequest(user_intent="test", user_id="user-001")
        client.match(request)

        _, kwargs = mock_request.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer my-key"

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_match_request_exception(self, mock_request):
        import requests as req_lib
        mock_request.side_effect = req_lib.RequestException("Connection error")

        client = MatcherClient()
        request = MatchRequest(user_intent="test", user_id="user-001")
        result = client.match(request)

        assert result.request_id == "local"
        assert result.candidates == []
        assert result.best_match is None
        assert result.total_available == 0

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_match_http_error(self, mock_request):
        import requests as req_lib
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req_lib.HTTPError("500 error")
        mock_request.return_value = mock_resp

        client = MatcherClient()
        request = MatchRequest(user_intent="test", user_id="user-001")
        result = client.match(request)

        assert result.request_id == "local"
        assert result.candidates == []

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_match_appends_to_history(self, mock_request):
        mock_resp = self._make_mock_response([
            {"skill_id": "skill-001", "skill_name": "Test", "score": 0.9},
        ])
        mock_request.return_value = mock_resp

        client = MatcherClient()
        request = MatchRequest(user_intent="test", user_id="user-001")
        client.match(request)

        assert len(client.get_match_history()) == 1

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_match_history_is_copy(self, mock_request):
        mock_resp = self._make_mock_response([])
        mock_request.return_value = mock_resp

        client = MatcherClient()
        request = MatchRequest(user_intent="test", user_id="user-001")
        client.match(request)

        history = client.get_match_history()
        history.clear()

        assert len(client.get_match_history()) == 1

    def test_match_time_ms_positive(self):
        with patch("skillos.protocol.matcher_client.requests.request") as mock_request:
            mock_resp = self._make_mock_response([])
            mock_request.return_value = mock_resp

            client = MatcherClient()
            request = MatchRequest(user_intent="test", user_id="user-001")
            result = client.match(request)

            assert result.match_time_ms >= 0


class TestMatcherClientReportOutcome:
    @patch("skillos.protocol.matcher_client.requests.request")
    def test_report_success(self, mock_request):
        mock_resp = MagicMock(status_code=200)
        mock_request.return_value = mock_resp

        client = MatcherClient()
        result = client.report_outcome("skill-001", success=True, rating=5.0)

        assert result is True

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_report_failure(self, mock_request):
        mock_resp = MagicMock(status_code=500)
        mock_request.return_value = mock_resp

        client = MatcherClient()
        result = client.report_outcome("skill-001", success=False)

        assert result is False

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_report_exception(self, mock_request):
        import requests as req_lib
        mock_request.side_effect = req_lib.RequestException("Network error")

        client = MatcherClient()
        result = client.report_outcome("skill-001", success=True)

        assert result is False

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_report_sends_correct_payload(self, mock_request):
        mock_resp = MagicMock(status_code=200)
        mock_request.return_value = mock_resp

        client = MatcherClient()
        client.report_outcome("skill-xyz", success=False, rating=2.0)

        _, kwargs = mock_request.call_args
        params = kwargs["json"]["params"]
        assert params["skill_id"] == "skill-xyz"
        assert params["success"] is False
        assert params["rating"] == 2.0

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_report_with_auth(self, mock_request):
        mock_resp = MagicMock(status_code=200)
        mock_request.return_value = mock_resp

        client = MatcherClient(api_key="key-123")
        client.report_outcome("skill-001", success=True)

        _, kwargs = mock_request.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer key-123"

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_report_default_rating(self, mock_request):
        mock_resp = MagicMock(status_code=200)
        mock_request.return_value = mock_resp

        client = MatcherClient()
        client.report_outcome("skill-001", success=True)

        _, kwargs = mock_request.call_args
        assert kwargs["json"]["params"]["rating"] == 0.0
