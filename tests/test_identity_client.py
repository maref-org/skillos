"""Tests for skillos.protocol.identity_client - Identity management"""

import base64
import os

import pytest

from skillos.protocol.identity_client import IdentityClient, IdentityRecord, Signature


# A valid Ed25519 public key PEM for tests that need an external key
VALID_ED25519_PUBLIC_KEY_PEM = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MCowBQYDK2VwAyEAj3x3g+rnjsqWGYXW3kZ9X+0PqRz0XqRz0XqRz0XqRz0=\n"
    "-----END PUBLIC KEY-----\n"
)


class TestIdentityRecord:
    def test_basic_fields(self):
        record = IdentityRecord(
            identity_id="id-001",
            public_key_pem="pem-key-string",
            role="creator",
            verified=False,
        )
        assert record.identity_id == "id-001"
        assert record.public_key_pem == "pem-key-string"
        assert record.role == "creator"
        assert record.verified is False

    def test_default_timestamp(self):
        record = IdentityRecord(
            identity_id="id-001",
            public_key_pem="pem",
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
        assert client._api_key is None
        assert client._identities == {}

    def test_custom_init(self):
        client = IdentityClient(base_url="https://example.com", api_key="key-123")
        assert client.base_url == "https://example.com"
        assert client._api_key == "key-123"

    def test_http_without_insecure_flag_raises(self):
        with pytest.raises(ValueError):
            IdentityClient(base_url="http://example.com")

    def test_http_with_insecure_flag_allowed(self, monkeypatch):
        monkeypatch.setenv("SKILLOS_INSECURE", "1")
        client = IdentityClient(base_url="http://example.com")
        assert client.base_url == "http://example.com"


class TestIdentityClientRegisterIdentity:
    def test_register_basic(self):
        client = IdentityClient()
        record = client.register_identity("user-001", "creator")

        assert record.identity_id == "user-001"
        assert record.role == "creator"
        assert record.verified is False
        assert record.public_key_pem.startswith("-----BEGIN PUBLIC KEY-----")

    def test_register_with_provided_pem(self):
        client = IdentityClient()
        record = client.register_identity("user-001", "creator", VALID_ED25519_PUBLIC_KEY_PEM)

        assert record.public_key_pem == VALID_ED25519_PUBLIC_KEY_PEM

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

    def test_different_identities_get_different_keys(self):
        client = IdentityClient()
        r1 = client.register_identity("user-001", "creator")
        r2 = client.register_identity("user-002", "creator")

        assert r1.public_key_pem != r2.public_key_pem

    def test_register_invalid_pem_raises(self):
        client = IdentityClient()
        with pytest.raises(ValueError):
            client.register_identity("user-001", "creator", public_key_pem="not-a-pem")

    def test_register_empty_identity_id_raises(self):
        client = IdentityClient()
        with pytest.raises(ValueError):
            client.register_identity("", "creator")

    def test_register_empty_role_raises(self):
        client = IdentityClient()
        with pytest.raises(ValueError):
            client.register_identity("user-001", "")


class TestIdentityClientVerifyIdentity:
    def test_verify_existing_identity(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")

        # Use the client's own private key to sign the challenge
        private_key = client._private_keys["user-001"]
        challenge = "challenge-123"
        challenge_signature = base64.b64encode(
            private_key.sign(challenge.encode("utf-8"))
        ).decode("ascii")

        result = client.verify_identity("user-001", challenge, challenge_signature)
        assert result is True

    def test_verify_nonexistent_identity(self):
        client = IdentityClient()
        result = client.verify_identity("nonexistent", "challenge-123", "sig")
        assert result is False

    def test_verify_sets_verified_flag(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")

        private_key = client._private_keys["user-001"]
        challenge = "challenge-123"
        challenge_signature = base64.b64encode(
            private_key.sign(challenge.encode("utf-8"))
        ).decode("ascii")

        client.verify_identity("user-001", challenge, challenge_signature)

        record = client.get_identity("user-001")
        assert record is not None
        assert record.verified is True

    def test_verify_before_and_after(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")

        record = client.get_identity("user-001")
        assert record is not None
        assert record.verified is False

        private_key = client._private_keys["user-001"]
        challenge = "challenge"
        challenge_signature = base64.b64encode(
            private_key.sign(challenge.encode("utf-8"))
        ).decode("ascii")

        client.verify_identity("user-001", challenge, challenge_signature)

        record = client.get_identity("user-001")
        assert record is not None
        assert record.verified is True

    def test_verify_with_external_key_no_private_key(self):
        client = IdentityClient()
        client.register_identity(
            "user-001", "creator", public_key_pem=VALID_ED25519_PUBLIC_KEY_PEM
        )

        # No private key available, so we can't produce a valid signature
        result = client.verify_identity("user-001", "challenge", "invalid-sig")
        assert result is False

    def test_verify_invalid_signature(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")

        result = client.verify_identity("user-001", "challenge", "invalid-sig")
        assert result is False


class TestIdentityClientSign:
    def test_sign_with_valid_identity(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")

        sig = client.sign("user-001", "some data to sign")

        assert sig is not None
        assert sig.signer_id == "user-001"
        # Ed25519 signatures are 64 bytes raw -> ~88 chars base64
        assert len(sig.signature) > 32
        assert isinstance(sig.data_hash, str)

    def test_sign_with_nonexistent_identity(self):
        client = IdentityClient()
        sig = client.sign("nonexistent", "data")
        assert sig is None

    def test_sign_different_data_different_signatures(self):
        client = IdentityClient()
        client.register_identity("user-001", "creator")

        sig1 = client.sign("user-001", "data-a")
        sig2 = client.sign("user-001", "data-b")

        assert sig1 is not None
        assert sig2 is not None
        assert sig1.data_hash != sig2.data_hash
        assert sig1.signature != sig2.signature

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

    def test_sign_external_identity_no_private_key(self):
        client = IdentityClient()
        client.register_identity(
            "user-001", "creator", public_key_pem=VALID_ED25519_PUBLIC_KEY_PEM
        )

        sig = client.sign("user-001", "data")
        assert sig is None


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

    def test_proof_contains_hash(self):
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
