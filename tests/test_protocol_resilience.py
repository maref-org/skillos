"""Tests for protocol client resilience — circuit breaker, retry, HTTPS, edge cases.

Phase 4.1: 补充协议客户端测试（覆盖率 40% → 80%）
"""

import time
from unittest.mock import MagicMock, patch

import pytest
import requests as req_lib

from skillos.protocol.identity_client import IdentityClient
from skillos.protocol.matcher_client import MatcherClient, MatchRequest
from skillos.protocol.registry_client import RegistryClient, RegistryConfig
from skillos.protocol.settlement_client import SettlementClient, SettlementRecord

# =============================================================================
# RegistryClient Resilience Tests
# =============================================================================


class TestRegistryCircuitBreaker:
    @patch("skillos.protocol.registry_client.requests.request")
    def test_circuit_opens_after_threshold(self, mock_request):
        mock_request.side_effect = req_lib.RequestException("Network error")
        client = RegistryClient()
        client.config.max_retries = 1
        client.config.retry_backoff = 0.0

        # Trigger failures to reach threshold (5)
        for _ in range(5):
            with pytest.raises(req_lib.RequestException):
                client._request_with_retry("GET", "https://example.com")

        assert client._is_circuit_open() is True

    @patch("skillos.protocol.registry_client.requests.request")
    def test_circuit_closes_after_timeout(self, mock_request):
        mock_request.side_effect = req_lib.RequestException("Network error")
        client = RegistryClient()
        client.config.max_retries = 1
        client.config.retry_backoff = 0.0
        client._circuit_timeout = 0.01  # 10ms for fast test

        for _ in range(5):
            with pytest.raises(req_lib.RequestException):
                client._request_with_retry("GET", "https://example.com")

        assert client._is_circuit_open() is True
        time.sleep(0.02)
        assert client._is_circuit_open() is False

    @patch("skillos.protocol.registry_client.requests.request")
    def test_circuit_records_success_resets_failures(self, mock_request):
        mock_resp = MagicMock()
        mock_request.return_value = mock_resp
        client = RegistryClient()

        client._circuit_failures = 3
        client._request_with_retry("GET", "https://example.com")
        assert client._circuit_failures == 0

    @patch("skillos.protocol.registry_client.requests.request")
    def test_request_blocked_when_circuit_open(self, mock_request):
        client = RegistryClient()
        client._circuit_failures = 5
        client._circuit_last_failure = time.time()

        with pytest.raises(req_lib.RequestException, match="Circuit breaker is open"):
            client._request_with_retry("GET", "https://example.com")

        mock_request.assert_not_called()


class TestRegistryRetryLogic:
    @patch("skillos.protocol.registry_client.requests.request")
    def test_retry_attempts_count(self, mock_request):
        mock_request.side_effect = req_lib.RequestException("Error")
        client = RegistryClient()
        client.config.max_retries = 3
        client.config.retry_backoff = 0.001

        with pytest.raises(req_lib.RequestException):
            client._request_with_retry("GET", "https://example.com")

        assert mock_request.call_count == 3

    @patch("skillos.protocol.registry_client.requests.request")
    def test_retry_success_on_second_attempt(self, mock_request):
        mock_resp = MagicMock()
        mock_request.side_effect = [
            req_lib.RequestException("Error 1"),
            mock_resp,
        ]
        client = RegistryClient()
        client.config.retry_backoff = 0.001

        result = client._request_with_retry("GET", "https://example.com")
        assert result is mock_resp
        assert mock_request.call_count == 2

    @patch("skillos.protocol.registry_client.requests.request")
    def test_retry_backoff_increases(self, mock_request):
        mock_request.side_effect = req_lib.RequestException("Error")
        client = RegistryClient()
        client.config.max_retries = 3
        client.config.retry_backoff = 0.01

        with patch("skillos.protocol.registry_client.time.sleep") as mock_sleep:
            with pytest.raises(req_lib.RequestException):
                client._request_with_retry("GET", "https://example.com")

        sleeps = [call[0][0] for call in mock_sleep.call_args_list]
        # 3 attempts: sleep after attempt 0 and 1, then final failure on attempt 2 also sleeps before raising
        assert sleeps == [0.01, 0.02, 0.04]


class TestRegistryHttpsEnforcement:
    def test_enforce_https_adds_prefix(self):
        url = RegistryClient._enforce_https("example.com")
        assert url == "https://example.com"

    def test_enforce_https_keeps_https(self):
        url = RegistryClient._enforce_https("https://example.com")
        assert url == "https://example.com"

    def test_enforce_https_rejects_http_without_flag(self):
        with pytest.raises(ValueError, match="HTTP is not allowed"):
            RegistryClient._enforce_https("http://example.com")

    def test_enforce_https_allows_http_with_insecure_flag(self, monkeypatch):
        monkeypatch.setenv("SKILLOS_INSECURE", "1")
        url = RegistryClient._enforce_https("http://example.com")
        assert url == "http://example.com"

    def test_init_enforces_https(self):
        client = RegistryClient(config=RegistryConfig(base_url="example.com"))
        assert client.config.base_url == "https://example.com"


class TestRegistryInputValidation:
    def test_register_empty_id_raises(self):
        from skillos.types import SkillManifest

        client = RegistryClient()
        with pytest.raises(ValueError, match="manifest.id"):
            client.register(SkillManifest(id="", name="Test", version="1.0.0", author="a", description="d"))

    def test_register_empty_name_raises(self):
        from skillos.types import SkillManifest

        client = RegistryClient()
        with pytest.raises(ValueError, match="manifest.name"):
            client.register(SkillManifest(id="id", name="", version="1.0.0", author="a", description="d"))

    def test_get_skill_empty_id_raises(self):
        client = RegistryClient()
        with pytest.raises(ValueError, match="skill_id"):
            client.get_skill("")

    def test_search_empty_query_raises(self):
        client = RegistryClient()
        with pytest.raises(ValueError, match="query"):
            client.search("")

    def test_search_invalid_page_raises(self):
        client = RegistryClient()
        with pytest.raises(ValueError, match="page"):
            client.search("test", page=0)

    def test_search_invalid_per_page_raises(self):
        client = RegistryClient()
        with pytest.raises(ValueError, match="per_page"):
            client.search("test", per_page=0)
        with pytest.raises(ValueError, match="per_page"):
            client.search("test", per_page=101)

    def test_publish_empty_skill_id_raises(self):
        client = RegistryClient()
        with pytest.raises(ValueError, match="skill_id"):
            client.publish("", "1.0.0")

    def test_publish_empty_version_raises(self):
        client = RegistryClient()
        with pytest.raises(ValueError, match="version"):
            client.publish("skill", "")

    def test_deprecate_empty_skill_id_raises(self):
        client = RegistryClient()
        with pytest.raises(ValueError, match="skill_id"):
            client.deprecate("")

    def test_get_call_stats_empty_skill_id_raises(self):
        client = RegistryClient()
        with pytest.raises(ValueError, match="skill_id"):
            client.get_call_stats("")


class TestRegistryHttpStatusHandling:
    @patch("skillos.protocol.registry_client.requests.request")
    def test_get_skill_500_returns_none(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = req_lib.HTTPError("500")
        mock_request.return_value = mock_resp

        client = RegistryClient()
        result = client.get_skill("skill-001")
        assert result is None

    @patch("skillos.protocol.registry_client.requests.request")
    def test_search_500_returns_empty(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req_lib.HTTPError("500")
        mock_request.return_value = mock_resp

        client = RegistryClient()
        result = client.search("test")
        assert result.total == 0
        assert result.skills == []


# =============================================================================
# MatcherClient Resilience Tests
# =============================================================================


class TestMatcherCircuitBreaker:
    @patch("skillos.protocol.matcher_client.requests.request")
    def test_circuit_opens_after_threshold(self, mock_request):
        mock_request.side_effect = req_lib.RequestException("Error")
        client = MatcherClient()
        client.max_retries = 1
        client.retry_backoff = 0.0

        for _ in range(5):
            with pytest.raises(req_lib.RequestException):
                client._request_with_retry("GET", "https://example.com")

        assert client._is_circuit_open() is True

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_circuit_closes_after_timeout(self, mock_request):
        mock_request.side_effect = req_lib.RequestException("Error")
        client = MatcherClient()
        client.max_retries = 1
        client.retry_backoff = 0.0
        client._circuit_timeout = 0.01

        for _ in range(5):
            with pytest.raises(req_lib.RequestException):
                client._request_with_retry("GET", "https://example.com")

        assert client._is_circuit_open() is True
        time.sleep(0.02)
        assert client._is_circuit_open() is False

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_match_returns_fallback_when_circuit_open(self, mock_request):
        client = MatcherClient()
        client._circuit_failures = 5
        client._circuit_last_failure = time.time()

        request = MatchRequest(user_intent="test", user_id="user-001")
        result = client.match(request)

        assert result.request_id == "local"
        assert result.candidates == []
        mock_request.assert_not_called()


class TestMatcherRetryLogic:
    @patch("skillos.protocol.matcher_client.requests.request")
    def test_retry_attempts_count(self, mock_request):
        mock_request.side_effect = req_lib.RequestException("Error")
        client = MatcherClient()
        client.max_retries = 3
        client.retry_backoff = 0.001

        with pytest.raises(req_lib.RequestException):
            client._request_with_retry("GET", "https://example.com")

        assert mock_request.call_count == 3

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_retry_success_on_third_attempt(self, mock_request):
        mock_resp = MagicMock()
        mock_request.side_effect = [
            req_lib.RequestException("Error 1"),
            req_lib.RequestException("Error 2"),
            mock_resp,
        ]
        client = MatcherClient()
        client.retry_backoff = 0.001

        result = client._request_with_retry("GET", "https://example.com")
        assert result is mock_resp
        assert mock_request.call_count == 3


class TestMatcherHttpsEnforcement:
    def test_enforce_https_adds_prefix(self):
        url = MatcherClient._enforce_https("example.com")
        assert url == "https://example.com"

    def test_enforce_https_rejects_http(self):
        with pytest.raises(ValueError, match="HTTP is not allowed"):
            MatcherClient._enforce_https("http://example.com")

    def test_init_enforces_https(self):
        client = MatcherClient(base_url="example.com")
        assert client.base_url == "https://example.com"


class TestMatcherInputValidation:
    def test_match_empty_intent_raises(self):
        client = MatcherClient()
        with pytest.raises(ValueError, match="user_intent"):
            client.match(MatchRequest(user_intent="", user_id="user-001"))

    def test_match_empty_user_id_raises(self):
        client = MatcherClient()
        with pytest.raises(ValueError, match="user_id"):
            client.match(MatchRequest(user_intent="test", user_id=""))

    def test_match_invalid_max_results_raises(self):
        client = MatcherClient()
        with pytest.raises(ValueError, match="max_results"):
            client.match(MatchRequest(user_intent="test", user_id="user-001", max_results=0))
        with pytest.raises(ValueError, match="max_results"):
            client.match(MatchRequest(user_intent="test", user_id="user-001", max_results=101))

    def test_report_outcome_empty_skill_id_raises(self):
        client = MatcherClient()
        with pytest.raises(ValueError, match="skill_id"):
            client.report_outcome("", success=True)


class TestMatcherHttpStatusHandling:
    @patch("skillos.protocol.matcher_client.requests.request")
    def test_match_401_returns_fallback(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req_lib.HTTPError("401")
        mock_request.return_value = mock_resp

        client = MatcherClient()
        request = MatchRequest(user_intent="test", user_id="user-001")
        result = client.match(request)

        assert result.request_id == "local"
        assert result.candidates == []

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_match_403_returns_fallback(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req_lib.HTTPError("403")
        mock_request.return_value = mock_resp

        client = MatcherClient()
        request = MatchRequest(user_intent="test", user_id="user-001")
        result = client.match(request)

        assert result.request_id == "local"

    @patch("skillos.protocol.matcher_client.requests.request")
    def test_report_outcome_401_returns_false(self, mock_request):
        mock_resp = MagicMock(status_code=401)
        mock_request.return_value = mock_resp

        client = MatcherClient()
        result = client.report_outcome("skill-001", success=True)
        assert result is False


# =============================================================================
# SettlementClient Resilience Tests
# =============================================================================


class TestSettlementCircuitBreaker:
    @patch("skillos.protocol.settlement_client.requests.request")
    def test_circuit_opens_after_threshold(self, mock_request):
        mock_request.side_effect = req_lib.RequestException("Error")
        client = SettlementClient()
        client.max_retries = 1
        client.retry_backoff = 0.0

        for _ in range(5):
            with pytest.raises(req_lib.RequestException):
                client._request_with_retry("GET", "https://example.com")

        assert client._is_circuit_open() is True

    @patch("skillos.protocol.settlement_client.requests.request")
    def test_circuit_closes_after_timeout(self, mock_request):
        mock_request.side_effect = req_lib.RequestException("Error")
        client = SettlementClient()
        client.max_retries = 1
        client.retry_backoff = 0.0
        client._circuit_timeout = 0.01

        for _ in range(5):
            with pytest.raises(req_lib.RequestException):
                client._request_with_retry("GET", "https://example.com")

        assert client._is_circuit_open() is True
        time.sleep(0.02)
        assert client._is_circuit_open() is False

    @patch("skillos.protocol.settlement_client.requests.request")
    def test_submit_record_returns_false_when_circuit_open(self, mock_request):
        client = SettlementClient()
        client._circuit_failures = 5
        client._circuit_last_failure = time.time()

        record = SettlementRecord(
            skill_call_id="call-001",
            skill_id="skill-001",
            caller_id="caller-001",
            amount_usd=1.0,
        )
        result = client.submit_record(record)
        assert result is False


class TestSettlementRetryLogic:
    @patch("skillos.protocol.settlement_client.requests.request")
    def test_retry_attempts_count(self, mock_request):
        mock_request.side_effect = req_lib.RequestException("Error")
        client = SettlementClient()
        client.max_retries = 3
        client.retry_backoff = 0.001

        with pytest.raises(req_lib.RequestException):
            client._request_with_retry("GET", "https://example.com")

        assert mock_request.call_count == 3

    @patch("skillos.protocol.settlement_client.requests.request")
    def test_retry_success_on_second_attempt(self, mock_request):
        mock_resp = MagicMock()
        mock_request.side_effect = [
            req_lib.RequestException("Error 1"),
            mock_resp,
        ]
        client = SettlementClient()
        client.retry_backoff = 0.001

        result = client._request_with_retry("GET", "https://example.com")
        assert result is mock_resp
        assert mock_request.call_count == 2


class TestSettlementHttpsEnforcement:
    def test_enforce_https_adds_prefix(self):
        url = SettlementClient._enforce_https("example.com")
        assert url == "https://example.com"

    def test_enforce_https_rejects_http(self):
        with pytest.raises(ValueError, match="HTTP is not allowed"):
            SettlementClient._enforce_https("http://example.com")

    def test_init_enforces_https(self):
        client = SettlementClient(base_url="example.com")
        assert client.base_url == "https://example.com"


class TestSettlementInputValidation:
    def test_submit_record_empty_call_id_raises(self):
        client = SettlementClient()
        with pytest.raises(ValueError, match="skill_call_id"):
            client.submit_record(
                SettlementRecord(skill_call_id="", skill_id="skill-001", caller_id="caller-001", amount_usd=1.0)
            )

    def test_submit_record_empty_skill_id_raises(self):
        client = SettlementClient()
        with pytest.raises(ValueError, match="skill_id"):
            client.submit_record(
                SettlementRecord(skill_call_id="call-001", skill_id="", caller_id="caller-001", amount_usd=1.0)
            )

    def test_submit_record_negative_amount_raises(self):
        client = SettlementClient()
        with pytest.raises(ValueError, match="amount_usd"):
            client.submit_record(
                SettlementRecord(
                    skill_call_id="call-001", skill_id="skill-001", caller_id="caller-001", amount_usd=-0.01
                )
            )

    def test_compute_split_negative_amount_raises(self):
        client = SettlementClient()
        with pytest.raises(ValueError, match="amount_usd"):
            client.compute_split(-1.0)

    def test_get_settlement_status_empty_period_raises(self):
        client = SettlementClient()
        with pytest.raises(ValueError, match="period"):
            client.get_settlement_status("")

    def test_trigger_settlement_invalid_period_raises(self):
        client = SettlementClient()
        with pytest.raises(ValueError, match="period_start"):
            client.trigger_settlement(period_start=2000.0, period_end=1000.0)
        with pytest.raises(ValueError, match="period_start"):
            client.trigger_settlement(period_start=1000.0, period_end=1000.0)


class TestSettlementBoundaryValues:
    def test_submit_record_zero_amount_auto_settles(self):
        client = SettlementClient()
        record = SettlementRecord(
            skill_call_id="call-zero", skill_id="skill-001", caller_id="caller-001", amount_usd=0.0
        )
        result = client.submit_record(record)
        assert result is True
        assert record.status == "auto_settled"

    def test_submit_record_just_above_threshold(self):
        client = SettlementClient()
        with patch("skillos.protocol.settlement_client.requests.request") as mock_request:
            mock_resp = MagicMock(status_code=200)
            mock_request.return_value = mock_resp
            record = SettlementRecord(
                skill_call_id="call-above", skill_id="skill-001", caller_id="caller-001", amount_usd=0.051
            )
            result = client.submit_record(record)
            assert result is True
            assert record.status == "submitted"

    def test_compute_split_large_amount(self):
        client = SettlementClient()
        split = client.compute_split(1_000_000.0)
        assert split["platform_fee"] == 50_000.0
        assert split["ecosystem_fee"] == 250_000.0
        assert split["contributor_pool"] == 700_000.0

    def test_compute_split_very_small_amount(self):
        client = SettlementClient()
        split = client.compute_split(0.001)
        total = sum(split.values())
        assert total == pytest.approx(0.001, abs=1e-6)


class TestSettlementHttpStatusHandling:
    @patch("skillos.protocol.settlement_client.requests.request")
    def test_get_status_500_returns_none(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_request.return_value = mock_resp

        client = SettlementClient()
        result = client.get_settlement_status("daily")
        assert result is None

    @patch("skillos.protocol.settlement_client.requests.request")
    def test_trigger_settlement_500_returns_none(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req_lib.HTTPError("500")
        mock_request.return_value = mock_resp

        client = SettlementClient()
        result = client.trigger_settlement(1000.0, 2000.0)
        assert result is None


# =============================================================================
# IdentityClient Resilience Tests
# =============================================================================


class TestIdentityHttpsEnforcement:
    def test_enforce_https_adds_prefix(self):
        url = IdentityClient._enforce_https("example.com")
        assert url == "https://example.com"

    def test_enforce_https_rejects_http(self):
        with pytest.raises(ValueError, match="HTTP is not allowed"):
            IdentityClient._enforce_https("http://example.com")

    def test_init_enforces_https(self):
        client = IdentityClient(base_url="example.com")
        assert client.base_url == "https://example.com"


class TestIdentityInputValidation:
    def test_register_identity_empty_id_raises(self):
        client = IdentityClient()
        with pytest.raises(ValueError, match="identity_id"):
            client.register_identity("", "creator")

    def test_register_identity_empty_role_raises(self):
        client = IdentityClient()
        with pytest.raises(ValueError, match="role"):
            client.register_identity("user-001", "")

    def test_register_identity_invalid_pem_raises(self):
        client = IdentityClient()
        with pytest.raises(ValueError, match="Invalid Ed25519"):
            client.register_identity("user-001", "creator", public_key_pem="not-a-pem")

    def test_verify_identity_empty_challenge_returns_false(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        result = client.verify_identity("user-001", "", "sig")
        assert result is False

    def test_sign_empty_data_returns_none(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        result = client.sign("user-001", "")
        assert result is None


class TestIdentityEdgeCases:
    def test_get_identity_nonexistent_returns_none(self):
        client = IdentityClient()
        assert client.get_identity("nonexistent") is None

    def test_generate_challenge_nonexistent_returns_error(self):
        client = IdentityClient()
        result = client.generate_challenge("nonexistent")
        assert result["valid"] is False

    def test_list_identities_empty(self):
        client = IdentityClient()
        assert client.list_identities() == []

    def test_signature_log_empty(self):
        client = IdentityClient()
        assert client.get_signature_log() == []

    def test_overwrite_identity(self):
        client = IdentityClient()
        r1 = client.register_identity("user-001", "creator")
        r2 = client.register_identity("user-001", "worker")
        assert client.get_identity("user-001").role == "worker"
        assert r1.public_key_pem != r2.public_key_pem

    def test_sign_and_verify_roundtrip(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")

        data = "important message"
        sig = client.sign("user-001", data)
        assert sig is not None
        assert client.verify_signature(sig, data) is True
        assert client.verify_signature(sig, "tampered") is False

    def test_multiple_identities_independent(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        client.register_identity("user-002", "worker")

        sig1 = client.sign("user-001", "data")
        sig2 = client.sign("user-002", "data")

        assert sig1 is not None
        assert sig2 is not None
        assert sig1.signature != sig2.signature
        assert client.verify_signature(sig1, "data") is True
        assert client.verify_signature(sig2, "data") is True

    def test_signature_with_wrong_identity_fails(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        client.register_identity("user-002", "worker")

        sig = client.sign("user-001", "data")
        # Manually change signer_id to wrong identity
        sig.signer_id = "user-002"
        assert client.verify_signature(sig, "data") is False
