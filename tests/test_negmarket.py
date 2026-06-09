"""Tests for skillos.negmarket — Negative Sample Market"""

import tempfile
from pathlib import Path

import pytest

from skillos.negmarket import (
    AntiPatternGenerator,
    AntiPatternResult,
    AntiPatternSkill,
    DesensitizationPipeline,
    NegativeSample,
    SQLiteNegMarketStorage,
    ZKVerifier,
)
from skillos.negmarket.desensitizer import (
    DynamicMaskStep,
    LocalPIIReplaceStep,
)

# ---------------------------------------------------------------------------
# Models tests
# ---------------------------------------------------------------------------


class TestNegativeSample:
    def test_default_fields(self):
        sample = NegativeSample()
        assert sample.id
        assert sample.risk_level == "medium"
        assert sample.verification_status == "pending"
        assert sample.price_per_call == 0.1
        assert sample.desensitized_pattern == {}

    def test_custom_values(self):
        sample = NegativeSample(
            id="test-001",
            contributor_id="user-001",
            category="api_error",
            risk_level="high",
        )
        assert sample.id == "test-001"
        assert sample.contributor_id == "user-001"
        assert sample.category == "api_error"
        assert sample.risk_level == "high"

    def test_id_unique(self):
        ids = {NegativeSample().id for _ in range(100)}
        assert len(ids) == 100


class TestAntiPatternSkill:
    def test_default_fields(self):
        skill = AntiPatternSkill()
        assert skill.id
        assert skill.call_count == 0
        assert skill.revenue == 0.0

    def test_custom_values(self):
        skill = AntiPatternSkill(
            id="skill-001",
            sample_id="sample-001",
            generated_by="agent-001",
            call_count=5,
            revenue=10.0,
        )
        assert skill.id == "skill-001"
        assert skill.sample_id == "sample-001"
        assert skill.generated_by == "agent-001"
        assert skill.call_count == 5
        assert skill.revenue == 10.0


class TestAntiPatternResult:
    def test_default_fields(self):
        result = AntiPatternResult()
        assert result.risk_level == ""
        assert result.warning == ""
        assert result.anti_pattern_id == ""

    def test_custom_values(self):
        result = AntiPatternResult(
            risk_level="high",
            warning="test warning",
            anti_pattern_id="pat-001",
        )
        assert result.risk_level == "high"
        assert result.warning == "test warning"
        assert result.anti_pattern_id == "pat-001"


# ---------------------------------------------------------------------------
# Desensitizer tests
# ---------------------------------------------------------------------------


class TestLocalPIIReplaceStep:
    def test_replaces_email(self):
        step = LocalPIIReplaceStep()
        ctx = step.process(
            type(
                "ctx",
                (),
                {
                    "raw_text": "contact me at test@example.com",
                    "desensitized_text": "",
                    "contributor_id": "u1",
                    "category": "general",
                    "risk_level": "medium",
                    "extra": {},
                },
            )()
        )
        assert "<REDACTED:EMAIL>" in ctx.desensitized_text

    def test_replaces_phone(self):
        step = LocalPIIReplaceStep()
        ctx = step.process(
            type(
                "ctx",
                (),
                {
                    "raw_text": "call 13800138000 for help",
                    "desensitized_text": "",
                    "contributor_id": "u1",
                    "category": "general",
                    "risk_level": "medium",
                    "extra": {},
                },
            )()
        )
        assert "<REDACTED:PHONE>" in ctx.desensitized_text

    def test_replaces_ip(self):
        step = LocalPIIReplaceStep()
        ctx = step.process(
            type(
                "ctx",
                (),
                {
                    "raw_text": "server at 192.168.1.1 is down",
                    "desensitized_text": "",
                    "contributor_id": "u1",
                    "category": "general",
                    "risk_level": "medium",
                    "extra": {},
                },
            )()
        )
        assert "<REDACTED:IP>" in ctx.desensitized_text

    def test_no_pii_unchanged(self):
        step = LocalPIIReplaceStep()
        ctx = step.process(
            type(
                "ctx",
                (),
                {
                    "raw_text": "this is a normal error message",
                    "desensitized_text": "",
                    "contributor_id": "u1",
                    "category": "general",
                    "risk_level": "medium",
                    "extra": {},
                },
            )()
        )
        assert ctx.desensitized_text == "this is a normal error message"

    def test_tracks_pii_types(self):
        step = LocalPIIReplaceStep()
        ctx = step.process(
            type(
                "ctx",
                (),
                {
                    "raw_text": "email: a@b.com, phone: 13800138000",
                    "desensitized_text": "",
                    "contributor_id": "u1",
                    "category": "general",
                    "risk_level": "medium",
                    "extra": {},
                },
            )()
        )
        assert "email" in ctx.extra.get("pii_types_found", [])
        assert "phone" in ctx.extra.get("pii_types_found", [])


class TestDynamicMaskStep:
    def test_masks_pii_in_output(self):
        step = DynamicMaskStep()
        ctx = step.process(
            type(
                "ctx",
                (),
                {
                    "raw_text": "email a@b.com was used",
                    "desensitized_text": "email a@b.com was used",
                    "contributor_id": "u1",
                    "category": "general",
                    "risk_level": "medium",
                    "extra": {},
                },
            )()
        )
        assert "<REDACTED:EMAIL>" in ctx.desensitized_text
        assert "a@b.com" not in ctx.desensitized_text


class TestDesensitizationPipeline:
    @pytest.fixture
    def pipeline(self):
        return DesensitizationPipeline()

    def test_process_creates_sample(self, pipeline):
        sample = pipeline.process(
            raw_text="error: timeout at 192.168.1.1, contact admin@test.com",
            contributor_id="user-001",
            category="timeout",
        )
        assert isinstance(sample, NegativeSample)
        assert sample.contributor_id == "user-001"
        assert sample.category == "timeout"
        assert sample.original_hash
        assert sample.desensitized_pattern

    def test_pii_removed(self, pipeline):
        sample = pipeline.process(
            raw_text="call 13800138000 or email test@example.com",
            contributor_id="user-001",
        )
        # 动态脱敏应移除所有 PII
        assert "13800138000" not in sample.desensitized_pattern
        assert "test@example.com" not in sample.desensitized_pattern

    def test_anti_pattern_extracted(self, pipeline):
        sample = pipeline.process(
            raw_text="Request failed with timeout error after 30s",
            contributor_id="user-001",
            category="timeout",
        )
        assert "triggers" in sample.desensitized_pattern
        assert "suggested_action" in sample.desensitized_pattern
        assert sample.desensitized_pattern["category"] == "timeout"

    def test_custom_steps(self):
        step = LocalPIIReplaceStep()
        pipeline = DesensitizationPipeline(steps=[step])
        sample = pipeline.process(raw_text="email a@b.com", contributor_id="u1")
        assert isinstance(sample, NegativeSample)

    def test_default_risk_level(self, pipeline):
        sample = pipeline.process("test", "u1")
        assert sample.risk_level == "medium"


# ---------------------------------------------------------------------------
# ZK Verifier tests
# ---------------------------------------------------------------------------


class TestZKVerifier:
    @pytest.fixture
    def verifier(self):
        return ZKVerifier()

    def test_prove_returns_proof(self, verifier):
        proof = verifier.prove("sensitive data", "user-001")
        assert proof.proof_value
        assert proof.sample_id
        assert not proof.verified

    def test_verify_valid_proof(self, verifier):
        proof = verifier.prove("sensitive data", "user-001")
        data_hash = "sensitive data"
        import hashlib

        digest = hashlib.sha256(data_hash.encode()).hexdigest()
        assert verifier.verify(proof, "user-001", digest)

    def test_verify_wrong_contributor(self, verifier):
        proof = verifier.prove("sensitive data", "user-001")
        import hashlib

        digest = hashlib.sha256("sensitive data".encode()).hexdigest()
        assert not verifier.verify(proof, "user-002", digest)

    def test_verify_wrong_data(self, verifier):
        proof = verifier.prove("sensitive data", "user-001")
        import hashlib

        digest = hashlib.sha256("wrong data".encode()).hexdigest()
        assert not verifier.verify(proof, "user-001", digest)

    def test_verify_sets_flag(self, verifier):
        proof = verifier.prove("data", "u1")
        import hashlib

        digest = hashlib.sha256("data".encode()).hexdigest()
        verifier.verify(proof, "u1", digest)
        assert proof.verified


# ---------------------------------------------------------------------------
# Anti-Pattern Generator tests
# ---------------------------------------------------------------------------


class TestAntiPatternGenerator:
    @pytest.fixture
    def generator(self):
        return AntiPatternGenerator()

    @pytest.fixture
    def sample(self):
        return NegativeSample(
            id="sample-001",
            contributor_id="user-001",
            category="timeout",
            risk_level="high",
            desensitized_pattern={
                "category": "timeout",
                "risk_level": "high",
                "triggers": ["timeout", "error"],
                "suggested_action": "增加输入校验 + 重试机制 + 人工审核",
            },
        )

    def test_generate_creates_skill(self, generator, sample):
        skill = generator.generate(sample, "agent-001")
        assert isinstance(skill, AntiPatternSkill)
        assert skill.sample_id == "sample-001"
        assert skill.generated_by == "agent-001"

    def test_generate_manifest(self, generator, sample):
        skill = generator.generate(sample, "agent-001")
        assert "name" in skill.skill_manifest
        assert "anti-timeout" in skill.skill_manifest["name"]
        assert skill.skill_manifest["metadata"]["risk_level"] == "high"
        assert skill.skill_manifest["metadata"]["negmarket"] is True

    def test_generate_unique_ids(self, generator, sample):
        s1 = generator.generate(sample, "agent-001")
        s2 = generator.generate(sample, "agent-001")
        assert s1.id != s2.id

    def test_call_returns_result(self, generator, sample):
        skill = generator.generate(sample, "agent-001")
        result = generator.call(skill)
        assert isinstance(result, AntiPatternResult)
        assert result.risk_level == "high"
        assert result.warning
        assert result.anti_pattern_id == skill.id

    def test_call_low_risk(self, generator):
        low_sample = NegativeSample(
            id="low-001",
            category="info",
            risk_level="low",
            desensitized_pattern={"triggers": ["unknown"]},
        )
        skill = generator.generate(low_sample, "agent-001")
        result = generator.call(skill)
        assert result.risk_level == "low"

    def test_call_medium_risk(self, generator):
        med_sample = NegativeSample(
            id="med-001",
            category="warning",
            risk_level="medium",
            desensitized_pattern={"triggers": ["error"]},
        )
        skill = generator.generate(med_sample, "agent-001")
        result = generator.call(skill)
        assert result.risk_level == "medium"

    def test_call_includes_warning(self, generator, sample):
        skill = generator.generate(sample, "agent-001")
        result = generator.call(skill)
        assert "输入校验" in result.warning
        assert "重试机制" in result.warning
        assert "人工审核" in result.warning


# ---------------------------------------------------------------------------
# Storage tests
# ---------------------------------------------------------------------------


class TestSQLiteNegMarketStorage:
    @pytest.fixture
    def storage(self):
        tmp = tempfile.mktemp(suffix=".db")
        store = SQLiteNegMarketStorage(db_path=tmp)
        yield store
        Path(tmp).unlink(missing_ok=True)

    def test_save_and_get_sample(self, storage):
        sample = NegativeSample(
            id="s1",
            contributor_id="u1",
            original_hash="abc",
            encrypted_blob="encrypted",
            category="timeout",
            desensitized_pattern={"key": "value"},
        )
        storage.save_sample(sample)
        retrieved = storage.get_sample("s1")
        assert retrieved is not None
        assert retrieved.id == "s1"
        assert retrieved.contributor_id == "u1"
        assert retrieved.desensitized_pattern == {"key": "value"}

    def test_get_nonexistent_sample(self, storage):
        assert storage.get_sample("nonexistent") is None

    def test_list_samples(self, storage):
        storage.save_sample(NegativeSample(id="s1", category="timeout"))
        storage.save_sample(NegativeSample(id="s2", category="api_error"))
        all_samples = storage.list_samples()
        assert len(all_samples) == 2

    def test_list_samples_filter_category(self, storage):
        storage.save_sample(NegativeSample(id="s1", category="timeout"))
        storage.save_sample(NegativeSample(id="s2", category="api_error"))
        filtered = storage.list_samples(category="timeout")
        assert len(filtered) == 1
        assert filtered[0].id == "s1"

    def test_list_samples_filter_risk(self, storage):
        storage.save_sample(NegativeSample(id="s1", risk_level="high"))
        storage.save_sample(NegativeSample(id="s2", risk_level="low"))
        filtered = storage.list_samples(risk_level="high")
        assert len(filtered) == 1
        assert filtered[0].id == "s1"

    def test_save_and_get_anti_pattern(self, storage):
        skill = AntiPatternSkill(
            id="ap1",
            sample_id="s1",
            skill_manifest={"name": "anti-test"},
            generated_by="agent-001",
        )
        storage.save_anti_pattern(skill)
        retrieved = storage.get_anti_pattern("ap1")
        assert retrieved is not None
        assert retrieved.id == "ap1"
        assert retrieved.sample_id == "s1"

    def test_discover_anti_patterns(self, storage):
        storage.save_sample(NegativeSample(id="s1", category="timeout"))
        storage.save_sample(NegativeSample(id="s2", category="api_error"))
        storage.save_anti_pattern(AntiPatternSkill(id="ap1", sample_id="s1"))
        storage.save_anti_pattern(AntiPatternSkill(id="ap2", sample_id="s2"))
        skills = storage.discover_anti_patterns()
        assert len(skills) == 2

    def test_discover_filter_category(self, storage):
        storage.save_sample(NegativeSample(id="s1", category="timeout"))
        storage.save_sample(NegativeSample(id="s2", category="api_error"))
        storage.save_anti_pattern(AntiPatternSkill(id="ap1", sample_id="s1"))
        storage.save_anti_pattern(AntiPatternSkill(id="ap2", sample_id="s2"))
        skills = storage.discover_anti_patterns(category="timeout")
        assert len(skills) == 1
        assert skills[0].id == "ap1"

    def test_update_call_stats(self, storage):
        storage.save_anti_pattern(AntiPatternSkill(id="ap1", call_count=0, revenue=0.0))
        storage.update_call_stats("ap1", revenue=1.0)
        skill = storage.get_anti_pattern("ap1")
        assert skill is not None
        assert skill.call_count == 1
        assert skill.revenue == 1.0

    def test_encrypt_decrypt_roundtrip(self, storage):
        sample = NegativeSample(id="enc-test", contributor_id="u1")
        secret = "my-secret-key-12345"
        encrypted = storage.encrypt_for_sample(sample, secret)
        assert encrypted
        decrypted = storage.decrypt_sample(encrypted, secret, "enc-test")
        # encrypt_for_sample 加密的是 original_hash（空字符串）
        assert decrypted == ""


# ---------------------------------------------------------------------------
# Distribution engine integration test
# ---------------------------------------------------------------------------


class TestDistributionEngineIntegration:
    def test_allocate_negmarket_revenue(self):
        from skillos._types import Contributor
        from skillos.distribution.engine import DistributionEngine

        engine = DistributionEngine()
        engine.register_contributor(
            Contributor(
                contributor_id="user-001",
                name="tester",
            )
        )

        record = engine.allocate_negmarket_revenue(
            sample_id="sample-001",
            amount=100.0,
            contributor_id="user-001",
        )
        assert record.total_amount == 100.0
        assert record.platform_fee == 5.0
        assert record.ecosystem_fee == 25.0
        assert record.contributor_pool == 70.0
        # neg_market_acquisition = 5% of ecosystem fee = 5% of 25 = 1.25
        assert record.ecosystem_breakdown["neg_market_acquisition"] == pytest.approx(1.25, abs=1e-6)

    def test_negmarket_ecosystem_allocation_in_distribution(self):
        from skillos._types import SkillCall
        from skillos.distribution.engine import DistributionEngine

        engine = DistributionEngine()
        call = SkillCall(
            skill_id="negmarket:sample-001",
            caller_id="user-001",
            input_data={},
            revenue_usd=100.0,
            status="completed",
        )
        record = engine.distribute(call)
        negmarket_share = record.ecosystem_breakdown.get("neg_market_acquisition", 0)
        assert negmarket_share == pytest.approx(1.25, abs=1e-6)
