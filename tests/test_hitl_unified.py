"""Tests for unified HITL Interrupt API (confirm / reject / pause / cancel / await)

Validates P1 #2 fix: EntryKernel now provides a unified API for all four HITL
interrupt signals (confirm / reject / pause / cancel) plus async await_confirmation.
"""

import threading
import time

import pytest

from skillos._types import Intent, IntentType
from skillos.kernel.entry_kernel import EntryKernel
from skillos.types import ApprovalStatus


@pytest.fixture
def kernel():
    """Fresh EntryKernel for each test."""
    return EntryKernel()


@pytest.fixture
def high_risk_intent():
    """Intent that triggers high-risk human gate (PENDING)."""
    return Intent(
        intent_type=IntentType.EXECUTION,
        raw_input="delete all files and deploy",
        parsed_query="delete all files and deploy",
        confidence=0.9,
        requires_human_gate=True,
    )


@pytest.fixture
def medium_risk_intent():
    """Intent that triggers medium-risk human gate (PENDING)."""
    return Intent(
        intent_type=IntentType.EXECUTION,
        raw_input="update the configuration",
        parsed_query="update the configuration",
        confidence=0.85,
        requires_human_gate=True,
    )


@pytest.fixture
def low_risk_intent():
    """Intent that triggers low-risk auto-approve."""
    return Intent(
        intent_type=IntentType.CHAT,
        raw_input="hello world",
        parsed_query="hello world",
        confidence=0.95,
        requires_human_gate=False,
    )


@pytest.fixture
def mock_session_manager():
    """Mock SessionManager with pause/abort tracking."""
    manager = type("MockSessionManager", (), {})()
    manager.paused_sessions = []
    manager.aborted_sessions = []
    manager.pause_session = lambda sid: manager.paused_sessions.append(sid)
    manager.abort_session = lambda sid: manager.aborted_sessions.append(sid)
    return manager


class TestConfirmApproval:
    """Test confirm_approval() — PENDING → APPROVED."""

    def test_confirm_pending_approval(self, kernel, high_risk_intent):
        """PENDING approval can be confirmed."""
        approval = kernel.human_gate(high_risk_intent)
        assert approval.status == ApprovalStatus.PENDING

        confirmed = kernel.confirm_approval(approval.approval_id, decision_maker="alice")
        assert confirmed is not None
        assert confirmed.status == ApprovalStatus.APPROVED
        assert confirmed.human_decision == "confirmed"
        assert confirmed.decided_at is not None

    def test_confirm_nonexistent_id_returns_none(self, kernel):
        """Non-existent approval_id returns None."""
        result = kernel.confirm_approval("nonexistent-id")
        assert result is None

    def test_confirm_already_decided_returns_none(self, kernel, high_risk_intent):
        """Already-confirmed approval cannot be confirmed again."""
        approval = kernel.human_gate(high_risk_intent)
        kernel.confirm_approval(approval.approval_id)
        # Second confirm should fail
        result = kernel.confirm_approval(approval.approval_id)
        assert result is None

    def test_confirm_auto_approved_returns_none(self, kernel, low_risk_intent):
        """Auto-approved (non-PENDING) approvals are not registered and return None."""
        approval = kernel.human_gate(low_risk_intent)
        assert approval.status == ApprovalStatus.APPROVED
        # Auto-approved approvals are not in the registry
        result = kernel.confirm_approval(approval.approval_id)
        assert result is None


class TestRejectApproval:
    """Test reject_approval() — PENDING → REJECTED."""

    def test_reject_pending_approval(self, kernel, high_risk_intent):
        """PENDING approval can be rejected."""
        approval = kernel.human_gate(high_risk_intent)
        rejected = kernel.reject_approval(
            approval.approval_id,
            decision_maker="bob",
            reason="too dangerous",
        )
        assert rejected is not None
        assert rejected.status == ApprovalStatus.REJECTED
        assert rejected.human_decision == "rejected"
        assert "too dangerous" in (rejected.reasoning or "")

    def test_reject_nonexistent_id_returns_none(self, kernel):
        """Non-existent approval_id returns None."""
        result = kernel.reject_approval("nonexistent-id")
        assert result is None

    def test_reject_already_decided_returns_none(self, kernel, high_risk_intent):
        """Already-rejected approval cannot be rejected again."""
        approval = kernel.human_gate(high_risk_intent)
        kernel.reject_approval(approval.approval_id)
        result = kernel.reject_approval(approval.approval_id)
        assert result is None


class TestPauseForReview:
    """Test pause_for_review() — unified pause signal."""

    def test_pause_creates_pending_and_pauses_session(
        self, kernel, high_risk_intent, mock_session_manager
    ):
        """pause_for_review() creates PENDING approval and pauses session."""
        approval = kernel.pause_for_review(
            high_risk_intent, mock_session_manager, "session-001"
        )
        assert approval.status == ApprovalStatus.PENDING
        assert approval.session_id == "session-001"
        assert mock_session_manager.paused_sessions == ["session-001"]

    def test_pause_low_risk_does_not_pause_session(
        self, kernel, low_risk_intent, mock_session_manager
    ):
        """Low-risk intent auto-approves, no pause."""
        approval = kernel.pause_for_review(
            low_risk_intent, mock_session_manager, "session-002"
        )
        assert approval.status == ApprovalStatus.APPROVED
        assert mock_session_manager.paused_sessions == []


class TestCancelSession:
    """Test cancel_session() — unified cancel signal."""

    def test_cancel_rejects_pending_and_aborts(
        self, kernel, high_risk_intent, mock_session_manager
    ):
        """cancel_session() rejects pending approvals and aborts session."""
        approval = kernel.pause_for_review(
            high_risk_intent, mock_session_manager, "session-003"
        )
        assert approval.status == ApprovalStatus.PENDING

        result = kernel.cancel_session(
            mock_session_manager, "session-003", reason="user requested"
        )
        assert result is True
        assert mock_session_manager.aborted_sessions == ["session-003"]

        # Approval should now be REJECTED
        # Note: confirm_approval returns None for non-PENDING, so we check via get_pending
        pending = kernel.get_pending_approvals()
        assert all(a.session_id != "session-003" for a in pending)

    def test_cancel_without_pending_still_aborts(
        self, kernel, mock_session_manager
    ):
        """cancel_session() aborts even if no pending approvals exist."""
        result = kernel.cancel_session(
            mock_session_manager, "session-004", reason="cleanup"
        )
        assert result is True
        assert mock_session_manager.aborted_sessions == ["session-004"]


class TestAwaitConfirmation:
    """Test await_confirmation() — blocking wait with timeout."""

    def test_await_times_out(self, kernel, high_risk_intent):
        """await_confirmation() returns None on timeout."""
        approval = kernel.human_gate(high_risk_intent)
        result = kernel.await_confirmation(approval.approval_id, timeout=0.1)
        assert result is None

    def test_await_returns_after_confirm(self, kernel, high_risk_intent):
        """await_confirmation() returns APPROVED after confirm_approval()."""
        approval = kernel.human_gate(high_risk_intent)

        # Confirm in a separate thread after a short delay
        def confirm_after_delay():
            time.sleep(0.05)
            kernel.confirm_approval(approval.approval_id)

        threading.Thread(target=confirm_after_delay, daemon=True).start()

        result = kernel.await_confirmation(approval.approval_id, timeout=2.0)
        assert result is not None
        assert result.status == ApprovalStatus.APPROVED

    def test_await_returns_after_reject(self, kernel, high_risk_intent):
        """await_confirmation() returns REJECTED after reject_approval()."""
        approval = kernel.human_gate(high_risk_intent)

        def reject_after_delay():
            time.sleep(0.05)
            kernel.reject_approval(approval.approval_id, reason="rejected by test")

        threading.Thread(target=reject_after_delay, daemon=True).start()

        result = kernel.await_confirmation(approval.approval_id, timeout=2.0)
        assert result is not None
        assert result.status == ApprovalStatus.REJECTED

    def test_await_nonexistent_returns_none(self, kernel):
        """await_confirmation() for non-existent ID returns None."""
        result = kernel.await_confirmation("nonexistent-id", timeout=0.1)
        assert result is None

    def test_await_already_decided_returns_approval(self, kernel, high_risk_intent):
        """await_confirmation() for already-decided approval returns it immediately."""
        approval = kernel.human_gate(high_risk_intent)
        kernel.confirm_approval(approval.approval_id)

        # Should return immediately (event already popped)
        result = kernel.await_confirmation(approval.approval_id, timeout=0.1)
        assert result is not None
        assert result.status == ApprovalStatus.APPROVED


class TestGetPendingApprovals:
    """Test get_pending_approvals() — list pending approvals."""

    def test_empty_when_no_pending(self, kernel):
        """No pending approvals initially."""
        assert kernel.get_pending_approvals() == []

    def test_returns_pending_only(self, kernel, high_risk_intent, medium_risk_intent):
        """Only PENDING approvals are returned."""
        a1 = kernel.human_gate(high_risk_intent)
        a2 = kernel.human_gate(medium_risk_intent)

        pending = kernel.get_pending_approvals()
        assert len(pending) == 2

        # Confirm one
        kernel.confirm_approval(a1.approval_id)
        pending = kernel.get_pending_approvals()
        assert len(pending) == 1
        assert pending[0].approval_id == a2.approval_id


class TestApprovalDataclass:
    """Test extended Approval fields."""

    def test_approval_has_auto_generated_id(self, kernel, high_risk_intent):
        """Approval.approval_id is auto-generated UUID."""
        a1 = kernel.human_gate(high_risk_intent)
        a2 = kernel.human_gate(high_risk_intent)
        assert a1.approval_id != a2.approval_id
        assert len(a1.approval_id) > 0

    def test_approval_session_id_default_none(self, kernel, high_risk_intent):
        """Approval.session_id is None by default."""
        approval = kernel.human_gate(high_risk_intent)
        assert approval.session_id is None

    def test_approval_decided_at_set_on_confirm(self, kernel, high_risk_intent):
        """Approval.decided_at is set when confirmed."""
        approval = kernel.human_gate(high_risk_intent)
        assert approval.decided_at is None

        kernel.confirm_approval(approval.approval_id)
        # Re-fetch from internal dict
        stored = kernel._approvals.get(approval.approval_id)
        assert stored is not None
        assert stored.decided_at is not None
