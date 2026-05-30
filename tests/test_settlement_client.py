"""Tests for skillos.protocol.settlement_client - Settlement center with mocked requests"""

from unittest.mock import MagicMock, patch

import pytest

from skillos.protocol.settlement_client import (
    SettlementClient,
    SettlementRecord,
    SettlementReport,
)


class TestSettlementRecord:
    def test_basic_fields(self):
        record = SettlementRecord(
            skill_call_id="call-001",
            skill_id="skill-001",
            caller_id="caller-001",
            amount_usd=1.0,
            platform_fee=0.05,
            ecosystem_fee=0.25,
            contributor_pool=0.70,
        )
        assert record.skill_call_id == "call-001"
        assert record.status == "pending"
        assert record.timestamp > 0

    def test_custom_status(self):
        record = SettlementRecord(
            skill_call_id="call-001",
            skill_id="skill-001",
            caller_id="caller-001",
            amount_usd=1.0,
            platform_fee=0.05,
            ecosystem_fee=0.25,
            contributor_pool=0.70,
            status="settled",
        )
        assert record.status == "settled"


class TestSettlementReport:
    def test_basic_fields(self):
        report = SettlementReport(
            period_start=1000.0,
            period_end=2000.0,
            total_revenue=100.0,
            total_platform_fees=5.0,
            total_ecosystem_fees=25.0,
            total_contributor_payouts=70.0,
            record_count=10,
            status="completed",
        )
        assert report.total_revenue == 100.0
        assert report.status == "completed"


class TestSettlementClientInit:
    def test_default_init(self):
        client = SettlementClient()
        assert client.base_url == "http://localhost:8080"
        assert client.api_key is None
        assert client._pending_records == []
        assert client._settled_records == []

    def test_custom_init(self):
        client = SettlementClient(base_url="http://example.com", api_key="key-123")
        assert client.base_url == "http://example.com"
        assert client.api_key == "key-123"


class TestSettlementClientAuthHeaders:
    def test_without_api_key(self):
        client = SettlementClient()
        headers = client._auth_headers()
        assert headers == {"Content-Type": "application/json"}
        assert "Authorization" not in headers

    def test_with_api_key(self):
        client = SettlementClient(api_key="my-secret")
        headers = client._auth_headers()
        assert headers["Authorization"] == "Bearer my-secret"


class TestSettlementClientComputeSplit:
    def test_one_dollar_split(self):
        client = SettlementClient()
        split = client.compute_split(1.0)

        assert split["platform_fee"] == pytest.approx(0.05, abs=1e-6)
        assert split["ecosystem_fee"] == pytest.approx(0.25, abs=1e-6)
        assert split["contributor_pool"] == pytest.approx(0.70, abs=1e-6)

    def test_split_sums_to_total(self):
        client = SettlementClient()
        split = client.compute_split(100.0)

        total = split["platform_fee"] + split["ecosystem_fee"] + split["contributor_pool"]
        assert total == pytest.approx(100.0, abs=1e-4)

    def test_zero_amount(self):
        client = SettlementClient()
        split = client.compute_split(0.0)

        assert split["platform_fee"] == 0.0
        assert split["ecosystem_fee"] == 0.0
        assert split["contributor_pool"] == 0.0

    def test_micro_amount(self):
        client = SettlementClient()
        split = client.compute_split(0.01)

        assert split["platform_fee"] > 0
        assert split["ecosystem_fee"] > 0
        assert split["contributor_pool"] > 0

    @pytest.mark.parametrize(
        "amount,expected_platform,expected_ecosystem,expected_contributor",
        [
            (1.0, 0.05, 0.25, 0.70),
            (10.0, 0.5, 2.5, 7.0),
            (100.0, 5.0, 25.0, 70.0),
            (0.5, 0.025, 0.125, 0.35),
        ],
    )
    def test_5_25_70_parametrized(self, amount, expected_platform, expected_ecosystem, expected_contributor):
        client = SettlementClient()
        split = client.compute_split(amount)

        assert split["platform_fee"] == pytest.approx(expected_platform, abs=1e-6)
        assert split["ecosystem_fee"] == pytest.approx(expected_ecosystem, abs=1e-6)
        assert split["contributor_pool"] == pytest.approx(expected_contributor, abs=1e-6)


class TestSettlementClientSubmitRecord:
    @patch("skillos.protocol.settlement_client.requests.post")
    def test_submit_large_amount_goes_remote(self, mock_post):
        mock_resp = MagicMock(status_code=200)
        mock_post.return_value = mock_resp

        client = SettlementClient()
        record = SettlementRecord(
            skill_call_id="call-001",
            skill_id="skill-001",
            caller_id="caller-001",
            amount_usd=1.0,
            platform_fee=0.0,
            ecosystem_fee=0.0,
            contributor_pool=0.0,
        )

        result = client.submit_record(record)
        assert result is True

    @patch("skillos.protocol.settlement_client.requests.post")
    def test_submit_small_amount_auto_settles(self, mock_post):
        client = SettlementClient()
        record = SettlementRecord(
            skill_call_id="call-small",
            skill_id="skill-001",
            caller_id="caller-001",
            amount_usd=0.01,
            platform_fee=0.0,
            ecosystem_fee=0.0,
            contributor_pool=0.0,
        )

        result = client.submit_record(record)
        assert result is True

        mock_post.assert_not_called()

    def test_submit_exact_threshold_auto_settles(self):
        client = SettlementClient()
        record = SettlementRecord(
            skill_call_id="call-threshold",
            skill_id="skill-001",
            caller_id="caller-001",
            amount_usd=0.05,
            platform_fee=0.0,
            ecosystem_fee=0.0,
            contributor_pool=0.0,
        )

        result = client.submit_record(record)
        assert result is True
        assert record.status == "auto_settled"

    def test_submit_above_threshold_goes_remote(self):
        client = SettlementClient()

        with patch("skillos.protocol.settlement_client.requests.post") as mock_post:
            mock_resp = MagicMock(status_code=200)
            mock_post.return_value = mock_resp

            record = SettlementRecord(
                skill_call_id="call-large",
                skill_id="skill-001",
                caller_id="caller-001",
                amount_usd=0.06,
                platform_fee=0.0,
                ecosystem_fee=0.0,
                contributor_pool=0.0,
            )

            result = client.submit_record(record)
            assert result is True
            assert record.status == "submitted"

    def test_submit_populates_fees(self):
        client = SettlementClient()
        record = SettlementRecord(
            skill_call_id="call-fees",
            skill_id="skill-001",
            caller_id="caller-001",
            amount_usd=10.0,
            platform_fee=0.0,
            ecosystem_fee=0.0,
            contributor_pool=0.0,
        )

        with patch("skillos.protocol.settlement_client.requests.post") as mock_post:
            mock_resp = MagicMock(status_code=200)
            mock_post.return_value = mock_resp
            client.submit_record(record)

        assert record.platform_fee == pytest.approx(0.5, abs=1e-6)
        assert record.ecosystem_fee == pytest.approx(2.5, abs=1e-6)
        assert record.contributor_pool == pytest.approx(7.0, abs=1e-6)

    @patch("skillos.protocol.settlement_client.requests.post")
    def test_submit_remote_failure(self, mock_post):
        import requests as req_lib
        mock_post.side_effect = req_lib.RequestException("Error")

        client = SettlementClient()
        record = SettlementRecord(
            skill_call_id="call-fail",
            skill_id="skill-001",
            caller_id="caller-001",
            amount_usd=1.0,
            platform_fee=0.0,
            ecosystem_fee=0.0,
            contributor_pool=0.0,
        )

        result = client.submit_record(record)
        assert result is False

    def test_submit_moved_to_pending(self):
        client = SettlementClient()
        record = SettlementRecord(
            skill_call_id="call-pending",
            skill_id="skill-001",
            caller_id="caller-001",
            amount_usd=1.0,
            platform_fee=0.0,
            ecosystem_fee=0.0,
            contributor_pool=0.0,
        )

        with patch("skillos.protocol.settlement_client.requests.post") as mock_post:
            mock_resp = MagicMock(status_code=200)
            mock_post.return_value = mock_resp
            client.submit_record(record)

        assert record not in client._pending_records
        assert record in client._settled_records

    def test_auto_settle_moved_to_settled(self):
        client = SettlementClient()
        record = SettlementRecord(
            skill_call_id="call-auto",
            skill_id="skill-001",
            caller_id="caller-001",
            amount_usd=0.03,
            platform_fee=0.0,
            ecosystem_fee=0.0,
            contributor_pool=0.0,
        )

        client.submit_record(record)

        assert record not in client._pending_records
        assert record in client._settled_records
        assert record.status == "auto_settled"

    @patch("skillos.protocol.settlement_client.requests.post")
    def test_submit_sends_correct_payload(self, mock_post):
        mock_resp = MagicMock(status_code=200)
        mock_post.return_value = mock_resp

        client = SettlementClient()
        record = SettlementRecord(
            skill_call_id="call-payload",
            skill_id="skill-xyz",
            caller_id="caller-abc",
            amount_usd=2.0,
            platform_fee=0.1,
            ecosystem_fee=0.5,
            contributor_pool=1.4,
        )

        client.submit_record(record)

        _, kwargs = mock_post.call_args
        params = kwargs["json"]["params"]
        assert params["skill_call_id"] == "call-payload"
        assert params["skill_id"] == "skill-xyz"
        assert params["caller_id"] == "caller-abc"
        assert params["amount_usd"] == 2.0

    @patch("skillos.protocol.settlement_client.requests.post")
    def test_submit_with_auth(self, mock_post):
        mock_resp = MagicMock(status_code=200)
        mock_post.return_value = mock_resp

        client = SettlementClient(api_key="auth-key")
        record = SettlementRecord(
            skill_call_id="call-auth",
            skill_id="skill-001",
            caller_id="caller-001",
            amount_usd=1.0,
            platform_fee=0.0,
            ecosystem_fee=0.0,
            contributor_pool=0.0,
        )

        client.submit_record(record)

        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer auth-key"


class TestSettlementClientGetSettlementStatus:
    @patch("skillos.protocol.settlement_client.requests.get")
    def test_get_status_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "period_start": 1000.0,
            "period_end": 2000.0,
            "total_revenue": 500.0,
            "platform_fees": 25.0,
            "ecosystem_fees": 125.0,
            "contributor_payouts": 350.0,
            "record_count": 50,
            "status": "completed",
        }
        mock_get.return_value = mock_resp

        client = SettlementClient()
        report = client.get_settlement_status("daily")

        assert report is not None
        assert report.total_revenue == 500.0
        assert report.total_platform_fees == 25.0
        assert report.total_ecosystem_fees == 125.0
        assert report.total_contributor_payouts == 350.0
        assert report.record_count == 50
        assert report.status == "completed"

    @patch("skillos.protocol.settlement_client.requests.get")
    def test_get_status_non_200(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        client = SettlementClient()
        report = client.get_settlement_status("daily")

        assert report is None

    @patch("skillos.protocol.settlement_client.requests.get")
    def test_get_status_network_error(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.RequestException("Timeout")

        client = SettlementClient()
        report = client.get_settlement_status("daily")

        assert report is None

    @patch("skillos.protocol.settlement_client.requests.get")
    def test_get_status_default_period(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        mock_get.return_value = mock_resp

        client = SettlementClient()
        client.get_settlement_status()

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["period"] == "daily"


class TestSettlementClientTriggerSettlement:
    @patch("skillos.protocol.settlement_client.requests.post")
    def test_trigger_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": {
                "total_revenue": 100.0,
                "platform_fees": 5.0,
                "ecosystem_fees": 25.0,
                "contributor_payouts": 70.0,
                "record_count": 10,
                "status": "completed",
            },
        }
        mock_post.return_value = mock_resp

        client = SettlementClient()
        report = client.trigger_settlement(period_start=1000.0, period_end=2000.0)

        assert report is not None
        assert report.total_revenue == 100.0
        assert report.period_start == 1000.0
        assert report.period_end == 2000.0
        assert report.status == "completed"

    @patch("skillos.protocol.settlement_client.requests.post")
    def test_trigger_failure(self, mock_post):
        import requests as req_lib
        mock_post.side_effect = req_lib.RequestException("Error")

        client = SettlementClient()
        report = client.trigger_settlement(1000.0, 2000.0)

        assert report is None

    @patch("skillos.protocol.settlement_client.requests.post")
    def test_trigger_sends_correct_payload(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {}}
        mock_post.return_value = mock_resp

        client = SettlementClient()
        client.trigger_settlement(period_start=100.0, period_end=200.0)

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["method"] == "settlement.trigger"
        assert kwargs["json"]["params"]["period_start"] == 100.0
        assert kwargs["json"]["params"]["period_end"] == 200.0


class TestSettlementClientGetPendingCount:
    def test_empty_pending(self):
        client = SettlementClient()
        assert client.get_pending_count() == 0

    def test_pending_count_after_submit(self):
        client = SettlementClient()

        with patch("skillos.protocol.settlement_client.requests.post") as mock_post:
            mock_resp = MagicMock(status_code=200)
            mock_post.return_value = mock_resp

            for i in range(3):
                record = SettlementRecord(
                    skill_call_id=f"call-{i}",
                    skill_id="skill-001",
                    caller_id="caller-001",
                    amount_usd=1.0,
                    platform_fee=0.0,
                    ecosystem_fee=0.0,
                    contributor_pool=0.0,
                )
                client.submit_record(record)

            assert client.get_pending_count() == 0
