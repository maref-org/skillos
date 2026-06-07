"""Tests for skillos.kernel.error_codes — Error Code Registry"""

from skillos.kernel.error_codes import (
    B001,
    B002,
    B003,
    C001,
    C002,
    C003,
    C004,
    D001,
    D002,
    D003,
    E000,
    E001,
    E002,
    E003,
    E004,
    E005,
    I001,
    I002,
    I003,
    I004,
    K001,
    K002,
    K003,
    K004,
    L001,
    L002,
    M001,
    M002,
    N001,
    N002,
    N003,
    N004,
    N005,
    N006,
    P001,
    P002,
    P003,
    R001,
    R002,
    R003,
    R004,
    R005,
    R006,
    S001,
    S002,
    S003,
    S004,
    S005,
    S006,
    T001,
    T002,
    T003,
    W001,
    W002,
    W003,
    ErrorCategory,
    ErrorCode,
    get_error_code,
    list_codes,
    lookup,
    register,
)


class TestErrorCodeStructure:
    def test_predefined_codes_exist(self):
        all_codes = [
            E000,
            E001,
            E002,
            E003,
            E004,
            E005,
            S001,
            S002,
            S003,
            S004,
            S005,
            S006,
            I001,
            I002,
            I003,
            I004,
            K001,
            K002,
            K003,
            K004,
            T001,
            T002,
            T003,
            P001,
            P002,
            P003,
            W001,
            W002,
            W003,
            R001,
            R002,
            R003,
            R004,
            R005,
            R006,
            L001,
            L002,
            D001,
            D002,
            D003,
            B001,
            B002,
            B003,
            M001,
            M002,
            C001,
            C002,
            C003,
            C004,
            N001,
            N002,
            N003,
            N004,
            N005,
            N006,
        ]
        assert len(all_codes) == 55
        for ec in all_codes:
            assert isinstance(ec, ErrorCode)
            assert ec.code.startswith("SKILLOS-")

    def test_no_duplicate_codes(self):
        codes = list_codes()
        identifiers = [c.code for c in codes]
        assert len(identifiers) == len(set(identifiers))

    def test_code_format(self):
        parts = E001.code.split("-")
        assert parts[0] == "SKILLOS"
        assert len(parts) == 4


class TestErrorCategory:
    def test_all_categories_present(self):
        categories = {ec.category for ec in list_codes()}
        assert ErrorCategory.SYSTEM in categories
        assert ErrorCategory.KERNEL in categories
        assert ErrorCategory.PROTOCOL in categories
        assert ErrorCategory.ECONOMIC in categories
        assert ErrorCategory.NEGMARKET in categories


class TestLookup:
    def test_lookup_existing(self):
        ec = lookup("SKILLOS-02-01-001")
        assert ec is not None
        assert ec.code == "SKILLOS-02-01-001"
        assert ec.category == ErrorCategory.KERNEL

    def test_lookup_nonexistent(self):
        assert lookup("SKILLOS-99-99-999") is None

    def test_lookup_empty_string(self):
        assert lookup("") is None

    def test_get_error_code(self):
        ec = get_error_code(ErrorCategory.PROTOCOL, 1, 1)
        assert ec is not None
        assert ec.code == "SKILLOS-03-01-001"

    def test_get_error_code_nonexistent(self):
        assert get_error_code(ErrorCategory.SYSTEM, 9, 9) is None


class TestRegister:
    def test_register_new_code(self):
        ec = register(ErrorCategory.SYSTEM, 9, 1, "Custom test error", 400)
        assert ec.code == "SKILLOS-01-09-001"
        assert ec.http_status == 400
        assert lookup(ec.code) is ec

    def test_register_duplicate_overwrites(self):
        ec1 = register(ErrorCategory.SYSTEM, 9, 2, "First")
        ec2 = register(ErrorCategory.SYSTEM, 9, 2, "Second")
        assert lookup(ec1.code) is ec2


class TestToDict:
    def test_to_dict_includes_all_fields(self):
        d = E001.to_dict()
        assert d["error_code"] == "SKILLOS-01-00-001"
        assert d["message"] == "Internal server error"
        assert d["category"] == "SYSTEM"
        assert d["http_status"] == 500

    def test_to_dict_404(self):
        d = E003.to_dict()
        assert d["http_status"] == 404
