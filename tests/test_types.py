"""Tests for skillos.types - Enums and Dataclasses"""

import time
import uuid

from skillos._types import (
    Approval,
    ApprovalStatus,
    Contributor,
    ExecutionPath,
    Intent,
    IntentType,
    ModelTier,
    Session,
    SessionStatus,
    SkillCall,
    SkillManifest,
    SkillStatus,
    Task,
)


class TestIntentTypeEnum:
    def test_intent_type_has_skill_call(self):
        assert IntentType.SKILL_CALL.value == "skill_call"

    def test_intent_type_has_research(self):
        assert IntentType.RESEARCH.value == "research"

    def test_intent_type_has_content_creation(self):
        assert IntentType.CONTENT_CREATION.value == "content_creation"

    def test_intent_type_has_analysis(self):
        assert IntentType.ANALYSIS.value == "analysis"

    def test_intent_type_has_execution(self):
        assert IntentType.EXECUTION.value == "execution"

    def test_intent_type_has_chat(self):
        assert IntentType.CHAT.value == "chat"

    def test_intent_type_count(self):
        assert len(IntentType) == 6

    def test_intent_type_from_string(self):
        assert IntentType("skill_call") == IntentType.SKILL_CALL

    def test_intent_type_str_representation(self):
        assert str(IntentType.RESEARCH) == "research"


class TestExecutionPathEnum:
    def test_human_gui(self):
        assert ExecutionPath.HUMAN_GUI.value == "human_gui"

    def test_agent_auto(self):
        assert ExecutionPath.AGENT_AUTO.value == "agent_auto"

    def test_hybrid(self):
        assert ExecutionPath.HYBRID.value == "hybrid"

    def test_execution_path_count(self):
        assert len(ExecutionPath) == 3


class TestApprovalStatusEnum:
    def test_approved(self):
        assert ApprovalStatus.APPROVED.value == "approved"

    def test_rejected(self):
        assert ApprovalStatus.REJECTED.value == "rejected"

    def test_pending(self):
        assert ApprovalStatus.PENDING.value == "pending"

    def test_approval_status_count(self):
        assert len(ApprovalStatus) == 3


class TestSkillStatusEnum:
    def test_draft(self):
        assert SkillStatus.DRAFT.value == "draft"

    def test_published(self):
        assert SkillStatus.PUBLISHED.value == "published"

    def test_deprecated(self):
        assert SkillStatus.DEPRECATED.value == "deprecated"

    def test_suspended(self):
        assert SkillStatus.SUSPENDED.value == "suspended"

    def test_skill_status_count(self):
        assert len(SkillStatus) == 4


class TestSessionStatusEnum:
    def test_active(self):
        assert SessionStatus.ACTIVE.value == "active"

    def test_paused(self):
        assert SessionStatus.PAUSED.value == "paused"

    def test_completed(self):
        assert SessionStatus.COMPLETED.value == "completed"

    def test_aborted(self):
        assert SessionStatus.ABORTED.value == "aborted"

    def test_session_status_count(self):
        assert len(SessionStatus) == 4


class TestModelTierEnum:
    def test_free(self):
        assert ModelTier.FREE.value == "free"

    def test_low(self):
        assert ModelTier.LOW.value == "low"

    def test_medium(self):
        assert ModelTier.MEDIUM.value == "medium"

    def test_high(self):
        assert ModelTier.HIGH.value == "high"

    def test_model_tier_count(self):
        assert len(ModelTier) == 4


class TestIntentDataclass:
    def test_basic_fields(self):
        intent = Intent(
            intent_type=IntentType.CHAT,
            raw_input="hello",
            parsed_query="hello",
            confidence=0.9,
        )
        assert intent.intent_type == IntentType.CHAT
        assert intent.raw_input == "hello"
        assert intent.parsed_query == "hello"
        assert intent.confidence == 0.9

    def test_requires_human_gate_default(self):
        intent = Intent(
            intent_type=IntentType.CHAT,
            raw_input="hello",
            parsed_query="hello",
            confidence=0.9,
        )
        assert intent.requires_human_gate is False

    def test_context_default_factory(self):
        intent = Intent(
            intent_type=IntentType.CHAT,
            raw_input="hello",
            parsed_query="hello",
            confidence=0.9,
        )
        assert intent.context == {}
        assert isinstance(intent.context, dict)

    def test_context_isolation(self):
        i1 = Intent(
            intent_type=IntentType.CHAT,
            raw_input="a",
            parsed_query="a",
            confidence=0.9,
        )
        i2 = Intent(
            intent_type=IntentType.CHAT,
            raw_input="b",
            parsed_query="b",
            confidence=0.9,
        )
        i1.context["key"] = "value"
        assert "key" not in i2.context

    def test_timestamp_default(self):
        before = time.time()
        intent = Intent(
            intent_type=IntentType.CHAT,
            raw_input="hello",
            parsed_query="hello",
            confidence=0.9,
        )
        after = time.time()
        assert before <= intent.timestamp <= after

    def test_custom_context(self):
        intent = Intent(
            intent_type=IntentType.ANALYSIS,
            raw_input="test",
            parsed_query="test",
            confidence=0.8,
            context={"source": "api"},
        )
        assert intent.context == {"source": "api"}


class TestApprovalDataclass:
    def test_basic_fields(self):
        approval = Approval(status=ApprovalStatus.APPROVED)
        assert approval.status == ApprovalStatus.APPROVED

    def test_human_decision_default(self):
        approval = Approval(status=ApprovalStatus.APPROVED)
        assert approval.human_decision is None

    def test_reasoning_default(self):
        approval = Approval(status=ApprovalStatus.APPROVED)
        assert approval.reasoning is None

    def test_timestamp_default(self):
        before = time.time()
        approval = Approval(status=ApprovalStatus.PENDING)
        after = time.time()
        assert before <= approval.timestamp <= after

    def test_full_fields(self):
        approval = Approval(
            status=ApprovalStatus.REJECTED,
            human_decision="not safe",
            reasoning="Risk too high",
        )
        assert approval.status == ApprovalStatus.REJECTED
        assert approval.human_decision == "not safe"
        assert approval.reasoning == "Risk too high"


class TestSkillManifestDataclass:
    def test_required_fields(self):
        manifest = SkillManifest(
            id="sk-001",
            name="test",
            version="1.0.0",
            author="dev",
            description="A test skill",
        )
        assert manifest.id == "sk-001"
        assert manifest.name == "test"
        assert manifest.version == "1.0.0"
        assert manifest.author == "dev"

    def test_license_default(self):
        manifest = SkillManifest(
            id="sk-001",
            name="test",
            version="1.0.0",
            author="dev",
            description="test",
        )
        assert manifest.license_type == "AGPL-3.0"

    def test_status_default(self):
        manifest = SkillManifest(
            id="sk-001",
            name="test",
            version="1.0.0",
            author="dev",
            description="test",
        )
        assert manifest.status == SkillStatus.DRAFT

    def test_entry_point_default(self):
        manifest = SkillManifest(
            id="sk-001",
            name="test",
            version="1.0.0",
            author="dev",
            description="test",
        )
        assert manifest.entry_point is None

    def test_dependencies_default_factory(self):
        manifest = SkillManifest(
            id="sk-001",
            name="test",
            version="1.0.0",
            author="dev",
            description="test",
        )
        assert manifest.dependencies == []

    def test_price_per_call_default(self):
        manifest = SkillManifest(
            id="sk-001",
            name="test",
            version="1.0.0",
            author="dev",
            description="test",
        )
        assert manifest.price_per_call == 0.0

    def test_metadata_default_factory(self):
        manifest = SkillManifest(
            id="sk-001",
            name="test",
            version="1.0.0",
            author="dev",
            description="test",
        )
        assert manifest.metadata == {}
        assert isinstance(manifest.metadata, dict)

    def test_created_at_timestamp(self):
        before = time.time()
        manifest = SkillManifest(
            id="sk-001",
            name="test",
            version="1.0.0",
            author="dev",
            description="test",
        )
        after = time.time()
        assert before <= manifest.created_at <= after

    def test_custom_values(self):
        manifest = SkillManifest(
            id="sk-001",
            name="pro-skill",
            version="2.0.0",
            author="pro-dev",
            description="Professional skill",
            license_type="MIT",
            status=SkillStatus.PUBLISHED,
            entry_point="main.py",
            dependencies=["numpy", "pandas"],
            price_per_call=0.01,
            metadata={"category": "analysis"},
        )
        assert manifest.license_type == "MIT"
        assert manifest.status == SkillStatus.PUBLISHED
        assert manifest.entry_point == "main.py"
        assert manifest.dependencies == ["numpy", "pandas"]
        assert manifest.price_per_call == 0.01
        assert manifest.metadata == {"category": "analysis"}

    def test_dependencies_isolation(self):
        m1 = SkillManifest(id="a", name="a", version="1.0", author="a", description="a")
        m2 = SkillManifest(id="b", name="b", version="1.0", author="b", description="b")
        m1.dependencies.append("dep")
        assert "dep" not in m2.dependencies


class TestSkillCallDataclass:
    def test_required_fields(self):
        call = SkillCall(
            skill_id="sk-001",
            caller_id="caller-001",
            input_data={"input": "test"},
        )
        assert call.skill_id == "sk-001"
        assert call.caller_id == "caller-001"
        assert call.input_data == {"input": "test"}

    def test_call_id_is_uuid(self):
        call = SkillCall(
            skill_id="sk-001",
            caller_id="caller-001",
            input_data={},
        )
        uuid.UUID(call.call_id)

    def test_call_id_unique(self):
        c1 = SkillCall(skill_id="a", caller_id="x", input_data={})
        c2 = SkillCall(skill_id="a", caller_id="x", input_data={})
        assert c1.call_id != c2.call_id

    def test_output_data_default(self):
        call = SkillCall(
            skill_id="sk-001",
            caller_id="caller-001",
            input_data={},
        )
        assert call.output_data is None

    def test_revenue_usd_default(self):
        call = SkillCall(
            skill_id="sk-001",
            caller_id="caller-001",
            input_data={},
        )
        assert call.revenue_usd == 0.0

    def test_status_default(self):
        call = SkillCall(
            skill_id="sk-001",
            caller_id="caller-001",
            input_data={},
        )
        assert call.status == "pending"

    def test_timestamp_default(self):
        before = time.time()
        call = SkillCall(skill_id="a", caller_id="x", input_data={})
        after = time.time()
        assert before <= call.timestamp <= after

    def test_latency_ms_default(self):
        call = SkillCall(
            skill_id="sk-001",
            caller_id="caller-001",
            input_data={},
        )
        assert call.latency_ms == 0.0


class TestTaskDataclass:
    def test_task_id_is_uuid(self):
        task = Task()
        uuid.UUID(task.task_id)

    def test_task_id_unique(self):
        t1 = Task()
        t2 = Task()
        assert t1.task_id != t2.task_id

    def test_description_default(self):
        assert Task().description == ""

    def test_complexity_default(self):
        assert Task().complexity == 0.5

    def test_required_model_tier_default(self):
        assert Task().required_model_tier == ModelTier.LOW

    def test_deadline_default(self):
        assert Task().deadline is None

    def test_metadata_default_factory(self):
        t1 = Task()
        t2 = Task()
        assert t1.metadata == {}
        assert isinstance(t1.metadata, dict)
        t1.metadata["key"] = "value"
        assert "key" not in t2.metadata

    def test_custom_values(self):
        import time

        task = Task(
            task_id="custom-id",
            description="do something",
            complexity=0.8,
            required_model_tier=ModelTier.HIGH,
            deadline=time.time() + 3600,
            metadata={"priority": "high"},
        )
        assert task.task_id == "custom-id"
        assert task.description == "do something"
        assert task.complexity == 0.8
        assert task.required_model_tier == ModelTier.HIGH
        assert task.metadata == {"priority": "high"}


class TestSessionDataclass:
    def test_session_id_is_uuid(self):
        session = Session()
        uuid.UUID(session.session_id)

    def test_session_id_unique(self):
        s1 = Session()
        s2 = Session()
        assert s1.session_id != s2.session_id

    def test_user_id_default(self):
        assert Session().user_id == ""

    def test_status_default_active(self):
        assert Session().status == SessionStatus.ACTIVE

    def test_items_default_factory(self):
        session = Session()
        assert session.items == []
        assert isinstance(session.items, list)

    def test_assets_default_factory(self):
        session = Session()
        assert session.assets == []
        assert isinstance(session.assets, list)

    def test_created_at_timestamp(self):
        before = time.time()
        session = Session()
        after = time.time()
        assert before <= session.created_at <= after

    def test_updated_at_timestamp(self):
        before = time.time()
        session = Session()
        after = time.time()
        assert before <= session.updated_at <= after

    def test_metadata_default_factory(self):
        s1 = Session()
        s2 = Session()
        s1.metadata["key"] = "val"
        assert "key" not in s2.metadata

    def test_items_isolation(self):
        s1 = Session()
        s2 = Session()
        s1.items.append({"data": 1})
        assert len(s2.items) == 0


class TestContributorDataclass:
    def test_required_fields(self):
        c = Contributor(contributor_id="c-001", name="Alice")
        assert c.contributor_id == "c-001"
        assert c.name == "Alice"

    def test_historical_contribution_default(self):
        c = Contributor(contributor_id="c-001", name="Alice")
        assert c.historical_contribution == 0.0

    def test_current_period_attribution_default(self):
        c = Contributor(contributor_id="c-001", name="Alice")
        assert c.current_period_attribution == 0.0

    def test_success_rate_default(self):
        c = Contributor(contributor_id="c-001", name="Alice")
        assert c.success_rate == 1.0

    def test_governance_participation_default(self):
        c = Contributor(contributor_id="c-001", name="Alice")
        assert c.governance_participation == 0.0

    def test_full_fields(self):
        c = Contributor(
            contributor_id="c-001",
            name="Alice",
            historical_contribution=0.9,
            current_period_attribution=0.5,
            success_rate=0.95,
            governance_participation=0.8,
        )
        assert c.historical_contribution == 0.9
        assert c.current_period_attribution == 0.5
        assert c.success_rate == 0.95
        assert c.governance_participation == 0.8
