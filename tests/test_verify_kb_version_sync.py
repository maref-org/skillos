"""Tests for scripts.verify_kb_version_sync"""



class TestGetCodeVersion:
    def test_reads_version_from_pyproject(self):
        from scripts.verify_kb_version_sync import get_code_version

        version = get_code_version()
        assert isinstance(version, str)
        assert len(version) > 0
        assert version.count(".") >= 2

    def test_version_matches_expected(self):
        from scripts.verify_kb_version_sync import get_code_version

        version = get_code_version()
        assert version.startswith("0.6")

    def test_scan_docs_returns_list(self):
        from scripts.verify_kb_version_sync import scan_docs

        result = scan_docs()
        assert isinstance(result, list)
