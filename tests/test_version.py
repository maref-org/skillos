"""Tests for version manager and rollback (Phase 5.2)."""

import tempfile

from skillos.version import VersionManager, get_version


class TestVersionManager:
    def test_record_deployment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = VersionManager(state_dir=tmpdir)
            state = mgr.record_deployment(
                version="0.3.0",
                alembic_revision="abc123",
                feature_flags={"new-ui": {"state": "enabled"}},
                deployed_by="ci",
            )
            assert state.version == "0.3.0"
            assert state.alembic_revision == "abc123"

    def test_get_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = VersionManager(state_dir=tmpdir)
            mgr.record_deployment("0.1.0", "rev1")
            mgr.record_deployment("0.2.0", "rev2")
            mgr.record_deployment("0.3.0", "rev3")

            history = mgr.get_history()
            assert len(history) == 3
            assert history[0].version == "0.3.0"  # 最新在前
            assert history[2].version == "0.1.0"

    def test_get_current_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = VersionManager(state_dir=tmpdir)
            assert mgr.get_current_version() is None

            mgr.record_deployment("0.3.0", "rev3")
            assert mgr.get_current_version() == "0.3.0"

    def test_get_previous_revision(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = VersionManager(state_dir=tmpdir)
            assert mgr.get_previous_revision() is None

            mgr.record_deployment("0.1.0", "rev1")
            mgr.record_deployment("0.2.0", "rev2")
            assert mgr.get_previous_revision() == "rev1"

    def test_prepare_rollback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = VersionManager(state_dir=tmpdir)
            mgr.record_deployment("0.1.0", "rev1", feature_flags={"flag-a": True})
            mgr.record_deployment("0.2.0", "rev2", feature_flags={"flag-a": False})

            info = mgr.prepare_rollback()
            assert info is not None
            assert info["from_version"] == "0.2.0"
            assert info["to_version"] == "0.1.0"
            assert info["from_revision"] == "rev2"
            assert info["to_revision"] == "rev1"
            assert info["feature_flags_to_restore"] == {"flag-a": True}

    def test_prepare_rollback_single_deployment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = VersionManager(state_dir=tmpdir)
            mgr.record_deployment("0.1.0", "rev1")
            assert mgr.prepare_rollback() is None

    def test_confirm_rollback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = VersionManager(state_dir=tmpdir)
            mgr.record_deployment("0.1.0", "rev1")
            mgr.record_deployment("0.2.0", "rev2")

            info = mgr.prepare_rollback()
            assert mgr.confirm_rollback(info) is True

            history = mgr.get_history()
            assert len(history) == 3
            assert history[0].deployed_by == "rollback"
            assert "0.2.0" in history[0].notes

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr1 = VersionManager(state_dir=tmpdir)
            mgr1.record_deployment("0.3.0", "rev1")

            mgr2 = VersionManager(state_dir=tmpdir)
            assert mgr2.get_current_version() == "0.3.0"

    def test_get_version(self):
        assert get_version() == "0.5.0-beta"
