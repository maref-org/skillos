"""Tests for skillos.protocol.identity_client - Ed25519-based identity management"""

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from skillos.protocol.identity_client import IdentityClient, IdentityRecord, Signature


def _generate_ed25519_pem() -> str:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


class TestIdentityRecord:
    def test_basic_fields(self):
        pem = _generate_ed25519_pem()
        record = IdentityRecord(
            identity_id="id-001",
            public_key_pem=pem,
            role="creator",
            verified=False,
        )
        assert record.identity_id == "id-001"
        assert record.public_key_pem == pem
        assert record.role == "creator"
        assert record.verified is False

    def test_default_timestamp(self):
        record = IdentityRecord(
            identity_id="id-001",
            public_key_pem=_generate_ed25519_pem(),
            role="creator",
            verified=True,
        )
        assert record.created_at > 0


class TestSignature:
    def test_basic_fields(self):
        sig = Signature(
            data_hash="hash123",
            signature="sig123",
            signer_id="signer-001",
        )
        assert sig.data_hash == "hash123"
        assert sig.signature == "sig123"
        assert sig.signer_id == "signer-001"

    def test_default_timestamp(self):
        sig = Signature(
            data_hash="hash123",
            signature="sig123",
            signer_id="signer-001",
        )
        assert sig.timestamp > 0


class TestIdentityClientInit:
    def test_default_init(self):
        client = IdentityClient()
        assert client.base_url == "https://localhost:8080"
        assert client._identities == {}

    def test_custom_init(self):
        client = IdentityClient(base_url="https://example.com", api_key="key-123")
        assert client.base_url == "https://example.com"
        assert client._api_key == "key-123"


class TestIdentityClientRegisterIdentity:
    def test_register_auto_generates_key(self):
        client = IdentityClient()
        record = client.register_identity("user-001", "creator")
        assert record.identity_id == "user-001"
        assert record.role == "creator"
        assert record.verified is False
        assert "BEGIN PUBLIC KEY" in record.public_key_pem

    def test_register_with_valid_pem(self):
        client = IdentityClient()
        pem = _generate_ed25519_pem()
        record = client.register_identity("user-001", "creator", public_key_pem=pem)
        assert record.public_key_pem == pem

    def test_register_with_invalid_pem_raises(self):
        client = IdentityClient()
        with pytest.raises(ValueError, match="Invalid Ed25519 public key PEM"):
            client.register_identity("user-001", "creator", "not-a-valid-pem")

    def test_same_pem_produces_same_identity(self):
        client = IdentityClient()
        pem = _generate_ed25519_pem()
        r1 = client.register_identity("user-001", "creator", public_key_pem=pem)
        r2 = client.register_identity("user-002", "worker", public_key_pem=pem)
        assert r1.public_key_pem == r2.public_key_pem

    def test_register_stores_identity(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        retrieved = client.get_identity("user-001")
        assert retrieved is not None
        assert retrieved.identity_id == "user-001"

    def test_register_different_roles(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        client.register_identity("user-002", "worker")
        client.register_identity("user-003", "platform")
        assert client.get_identity("user-001").role == "creator"
        assert client.get_identity("user-002").role == "worker"
        assert client.get_identity("user-003").role == "platform"

    def test_auto_generated_keys_are_unique(self):
        client = IdentityClient()
        r1 = client.register_identity("user-001", "creator")
        r2 = client.register_identity("user-002", "creator")
        assert r1.public_key_pem != r2.public_key_pem


class TestIdentityClientVerifyIdentity:
    def test_verify_valid_challenge_response(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        challenge = client.generate_challenge("user-001")["challenge"]
        sig = client.sign("user-001", challenge)
        assert sig is not None
        result = client.verify_identity("user-001", challenge, sig.signature)
        assert result is True

    def test_verify_nonexistent_identity(self):
        client = IdentityClient()
        result = client.verify_identity("nonexistent", "challenge", "sig")
        assert result is False

    def test_verify_sets_verified_flag(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        challenge = client.generate_challenge("user-001")["challenge"]
        sig = client.sign("user-001", challenge)
        assert sig is not None
        client.verify_identity("user-001", challenge, sig.signature)
        record = client.get_identity("user-001")
        assert record is not None
        assert record.verified is True

    def test_verify_invalid_signature(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        result = client.verify_identity("user-001", "challenge", "invalid-base64!")
        assert result is False


class TestIdentityClientSign:
    def test_sign_with_valid_identity(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        sig = client.sign("user-001", "some data to sign")
        assert sig is not None
        assert sig.signer_id == "user-001"
        assert isinstance(sig.data_hash, str)
        assert len(sig.data_hash) == 64

    def test_sign_with_nonexistent_identity(self):
        client = IdentityClient()
        sig = client.sign("nonexistent", "data")
        assert sig is None

    def test_sign_different_data_different_hashes(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        sig1 = client.sign("user-001", "data-a")
        sig2 = client.sign("user-001", "data-b")
        assert sig1 is not None
        assert sig2 is not None
        assert sig1.data_hash != sig2.data_hash

    def test_sign_stores_in_log(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        client.sign("user-001", "data")
        log = client.get_signature_log()
        assert len(log) == 1
        assert log[0].signer_id == "user-001"

    def test_multiple_signs_append_to_log(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        client.sign("user-001", "data-1")
        client.sign("user-001", "data-2")
        client.sign("user-001", "data-3")
        assert len(client.get_signature_log()) == 3


class TestIdentityClientVerifySignature:
    def test_verify_valid_signature(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        data = "important data"
        sig = client.sign("user-001", data)
        assert sig is not None
        assert client.verify_signature(sig, data) is True

    def test_verify_invalid_data(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        sig = client.sign("user-001", "original data")
        assert sig is not None
        assert client.verify_signature(sig, "tampered data") is False

    def test_verify_unknown_signer(self):
        client = IdentityClient()
        sig = Signature(
            data_hash="abc",
            signature="sig",
            signer_id="nonexistent",
        )
        assert client.verify_signature(sig, "data") is False

    def test_verify_with_multiple_identities(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        client.register_identity("user-002", "worker")
        sig = client.sign("user-001", "data")
        assert sig is not None
        assert client.verify_signature(sig, "data") is True


class TestIdentityClientGenerateChallenge:
    def test_generate_challenge_valid(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        result = client.generate_challenge("user-001")
        assert result["valid"] is True
        assert result["identity_id"] == "user-001"
        assert isinstance(result["challenge"], str)
        assert result["expires_at"] > 0

    def test_generate_challenge_nonexistent(self):
        client = IdentityClient()
        result = client.generate_challenge("nonexistent")
        assert result["valid"] is False
        assert result["error"] == "identity_not_found"


class TestIdentityClientGenerateZkProof:
    def test_valid_proof(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        proof = client.generate_zk_proof("user-001", "I am a creator")
        assert proof["valid"] is True
        assert "proof" in proof
        assert proof["claim"] == "I am a creator"
        assert proof["identity_id"] == "user-001"
        assert proof["timestamp"] > 0

    def test_invalid_proof_for_nonexistent(self):
        client = IdentityClient()
        proof = client.generate_zk_proof("nonexistent", "claim")
        assert proof["valid"] is False
        assert proof["error"] == "identity_not_found"

    def test_proof_is_hex_string(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        proof = client.generate_zk_proof("user-001", "claim")
        assert len(proof["proof"]) == 64

    def test_different_claims_different_proofs(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        proof1 = client.generate_zk_proof("user-001", "claim-a")
        proof2 = client.generate_zk_proof("user-001", "claim-b")
        assert proof1["proof"] != proof2["proof"]


class TestIdentityClientListIdentities:
    def test_list_empty(self):
        client = IdentityClient()
        assert client.list_identities() == []

    def test_list_all(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        client.register_identity("user-002", "worker")
        identities = client.list_identities()
        assert len(identities) == 2

    def test_list_filter_by_role(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        client.register_identity("user-002", "worker")
        client.register_identity("user-003", "creator")
        creators = client.list_identities(role="creator")
        assert len(creators) == 2
        workers = client.list_identities(role="worker")
        assert len(workers) == 1

    def test_list_filter_no_match(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        result = client.list_identities(role="platform")
        assert result == []


class TestIdentityClientGetSignatureLog:
    def test_get_all_logs(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        client.sign("user-001", "data")
        logs = client.get_signature_log()
        assert len(logs) == 1

    def test_get_logs_by_identity(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        client.register_identity("user-002", "worker")
        client.sign("user-001", "data-a")
        client.sign("user-002", "data-b")
        client.sign("user-001", "data-c")
        user1_logs = client.get_signature_log(identity_id="user-001")
        assert len(user1_logs) == 2

    def test_get_logs_nonexistent_identity(self):
        client = IdentityClient()
        logs = client.get_signature_log(identity_id="nonexistent")
        assert logs == []

    def test_log_is_copy(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")
        client.sign("user-001", "data")
        log1 = client.get_signature_log()
        log1.clear()
        assert len(client.get_signature_log()) == 1
