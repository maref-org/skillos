"""Integration tests — 端到端流程验证（使用真实内存数据库）

Phase 4.2: 集成测试
覆盖场景：
  1. Skill 完整生命周期（蒸馏 → NFT 铸造 → 工具链组装 → 状态管理）
  2. Session 完整生命周期（创建 → 添加 item → 暂停 → 恢复 → 完成）
  3. Distribution 端到端（Skill 调用 → 收入分配 → 贡献者注册 → 周期结算）
  4. Audit 链式验证（多组件操作 → 审计日志 → 链式校验）
  5. DB 持久化验证（写入 → 关闭 session → 新 session 读取 → 数据一致性）
"""

import asyncio
import tempfile
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from skillos.audit import AuditEventType, AuditLogger
from skillos.db.engine import Base
from skillos.db.models import ContributorModel, DistributionRecordModel, SessionModel, SkillModel, SkillNFTModel
from skillos.db.repository import ContributorRepository, DistributionRepository, SessionRepository, SkillNFTRepository, SkillRepository
from skillos.distribution.engine import DistributionEngine, SettlementPeriod
from skillos.kernel.session_manager import SessionManager
from skillos.kernel.skill_kernel import SkillKernel
from skillos.types import Contributor, SessionStatus, SkillCall, SkillManifest, SkillStatus


@pytest.fixture
def db_session():
    """提供真实内存数据库会话（每个测试独立）"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def audit_logger():
    """提供临时目录的审计日志器"""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = AuditLogger(log_dir=tmpdir, secret_key="test-secret-key-12345")
        yield logger


# =============================================================================
# Test 1: Skill 完整生命周期
# =============================================================================

class TestSkillLifecycle:
    def test_distill_persists_to_db(self, db_session):
        kernel = SkillKernel(db_session=db_session)
        manifest = kernel.distill("https://github.com/alice/cool-skill")

        assert manifest.id.startswith("skill-")
        assert manifest.name == "cool-skill"
        assert manifest.author == "alice"
        assert manifest.status == SkillStatus.DRAFT

        # 验证 DB 持久化
        repo = SkillRepository(db_session)
        model = repo.get(manifest.id)
        assert model is not None
        assert model.name == "cool-skill"
        assert model.status == "draft"

    def test_mint_nft_persists_to_db(self, db_session):
        kernel = SkillKernel(db_session=db_session)
        manifest = kernel.distill("https://github.com/bob/my-skill")
        nft = kernel.mint_nft(manifest)

        assert nft.skill_id == manifest.id
        assert nft.owner == manifest.author
        assert nft.token_id.startswith("nft-")

        # 验证 DB 持久化
        repo = SkillNFTRepository(db_session)
        models = repo.get_by_skill(manifest.id)
        assert len(models) == 1
        assert models[0].owner == "bob"

    def test_assemble_tools_requires_existing_skill(self, db_session):
        kernel = SkillKernel(db_session=db_session)
        manifest = kernel.distill("https://github.com/alice/skill-a")
        nft = kernel.mint_nft(manifest)

        tool_chain = kernel.assemble_tools(nft)
        assert tool_chain.skill_id == manifest.id
        assert len(tool_chain.tools) == 1
        assert tool_chain.execution_env == "wasm_sandbox"

    def test_assemble_tools_missing_skill_raises(self, db_session):
        kernel = SkillKernel(db_session=db_session)
        from skillos.kernel.skill_kernel import SkillNFT
        nft = SkillNFT(skill_id="nonexistent", token_id="nft-1", owner="x", metadata_hash="hash")

        with pytest.raises(ValueError, match="not found"):
            kernel.assemble_tools(nft)

    def test_get_skill_cache_then_db(self, db_session):
        kernel = SkillKernel(db_session=db_session)
        manifest = kernel.distill("https://github.com/alice/skill-b")

        # 第一次从缓存获取
        cached = kernel.get_skill(manifest.id)
        assert cached is not None
        assert cached.id == manifest.id

        # 清除缓存，强制从 DB 获取
        kernel._skill_cache.clear()
        from_db = kernel.get_skill(manifest.id)
        assert from_db is not None
        assert from_db.name == manifest.name

    def test_list_skills_filters_by_status(self, db_session):
        kernel = SkillKernel(db_session=db_session)
        kernel.distill("https://github.com/alice/skill-1")
        m2 = kernel.distill("https://github.com/alice/skill-2")
        kernel.update_status(m2.id, SkillStatus.PUBLISHED)

        drafts = kernel.list_skills(status=SkillStatus.DRAFT)
        published = kernel.list_skills(status=SkillStatus.PUBLISHED)

        assert len(drafts) >= 1
        assert len(published) == 1
        assert published[0].id == m2.id

    def test_update_status_syncs_cache_and_db(self, db_session):
        kernel = SkillKernel(db_session=db_session)
        manifest = kernel.distill("https://github.com/alice/skill-c")

        assert kernel.update_status(manifest.id, SkillStatus.PUBLISHED) is True

        # 缓存同步
        assert kernel._skill_cache[manifest.id].status == SkillStatus.PUBLISHED

        # DB 同步
        repo = SkillRepository(db_session)
        model = repo.get(manifest.id)
        assert model.status == "published"

    def test_update_status_nonexistent_returns_false(self, db_session):
        kernel = SkillKernel(db_session=db_session)
        assert kernel.update_status("nonexistent", SkillStatus.PUBLISHED) is False

    def test_execute_async(self, db_session):
        kernel = SkillKernel(db_session=db_session)
        manifest = kernel.distill("https://github.com/alice/skill-exec")
        nft = kernel.mint_nft(manifest)
        tool_chain = kernel.assemble_tools(nft)

        result = asyncio.run(kernel.execute(tool_chain, {"input": "hello"}))
        assert result["status"] == "completed"
        assert result["skill_id"] == manifest.id
        assert len(kernel._execution_log) == 1


# =============================================================================
# Test 2: Session 完整生命周期
# =============================================================================

class TestSessionLifecycle:
    def test_create_session_persists_to_db(self, db_session):
        manager = SessionManager(db_session=db_session)
        session = manager.create_session("user-001", metadata={"project": "test"})

        assert session.user_id == "user-001"
        assert session.status == SessionStatus.ACTIVE
        assert session.metadata == {"project": "test"}

        repo = SessionRepository(db_session)
        model = repo.get(session.session_id)
        assert model is not None
        assert model.user_id == "user-001"

    def test_add_item_updates_session_and_db(self, db_session):
        manager = SessionManager(db_session=db_session)
        session = manager.create_session("user-001")

        result = manager.add_item(session.session_id, {"role": "user", "content": "hello"})
        assert result is True
        assert len(session.items) == 1

        # 验证 DB 同步
        repo = SessionRepository(db_session)
        model = repo.get(session.session_id)
        assert len(model.items) == 1

    def test_add_item_to_paused_session_fails(self, db_session):
        manager = SessionManager(db_session=db_session)
        session = manager.create_session("user-001")
        manager.pause_session(session.session_id)

        result = manager.add_item(session.session_id, {"role": "user", "content": "hello"})
        assert result is False

    def test_pause_resume_cycle(self, db_session):
        manager = SessionManager(db_session=db_session)
        session = manager.create_session("user-001")

        assert manager.pause_session(session.session_id) is True
        assert session.status == SessionStatus.PAUSED

        assert manager.resume_session(session.session_id) is True
        assert session.status == SessionStatus.ACTIVE

        repo = SessionRepository(db_session)
        model = repo.get(session.session_id)
        assert model.status == "active"

    def test_complete_session(self, db_session):
        manager = SessionManager(db_session=db_session)
        session = manager.create_session("user-001")

        assert manager.complete_session(session.session_id) is True
        assert session.status == SessionStatus.COMPLETED

    def test_abort_session(self, db_session):
        manager = SessionManager(db_session=db_session)
        session = manager.create_session("user-001")

        assert manager.abort_session(session.session_id) is True
        assert session.status == SessionStatus.ABORTED

    def test_get_session_cache_then_db(self, db_session):
        manager = SessionManager(db_session=db_session)
        session = manager.create_session("user-001")
        sid = session.session_id

        # 从缓存获取
        cached = manager.get_session(sid)
        assert cached is not None

        # 清除缓存，从 DB 获取
        manager._sessions.clear()
        from_db = manager.get_session(sid)
        assert from_db is not None
        assert from_db.user_id == "user-001"

    def test_list_sessions_by_user(self, db_session):
        manager = SessionManager(db_session=db_session)
        s1 = manager.create_session("user-001")
        s2 = manager.create_session("user-001")
        manager.create_session("user-002")

        sessions = manager.list_sessions(user_id="user-001")
        assert len(sessions) == 2
        session_ids = {s.session_id for s in sessions}
        assert s1.session_id in session_ids
        assert s2.session_id in session_ids

    def test_search_sessions(self, db_session):
        manager = SessionManager(db_session=db_session)
        manager.create_session("user-001", metadata={"topic": "python"})
        manager.create_session("user-001", metadata={"topic": "javascript"})

        results = manager.search_sessions("user-001", "python")
        assert len(results) == 1
        assert results[0].metadata["topic"] == "python"

    def test_session_stats(self, db_session):
        manager = SessionManager(db_session=db_session)
        s1 = manager.create_session("user-001")
        manager.add_item(s1.session_id, {"role": "user", "content": "a"})
        manager.add_item(s1.session_id, {"role": "assistant", "content": "b"})
        manager.add_asset(s1.session_id, "asset-001")

        stats = manager.get_session_stats("user-001")
        assert stats["total_sessions"] == 1
        assert stats["total_items"] == 2
        assert stats["total_assets"] == 1
        assert stats["avg_items_per_session"] == 2.0

    def test_cleanup_expired_sessions(self, db_session):
        manager = SessionManager(db_session=db_session)
        session = manager.create_session("user-001")
        manager.complete_session(session.session_id)

        # 手动设置 updated_at 为很久以前
        model = db_session.query(SessionModel).filter_by(session_id=session.session_id).first()
        model.updated_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        db_session.commit()

        # 更新缓存中的时间
        manager._sessions[session.session_id].updated_at = datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp()

        count = manager.cleanup_expired(max_age_hours=1)
        assert count == 1
        assert session.session_id not in manager._sessions


# =============================================================================
# Test 3: Distribution 端到端
# =============================================================================

class TestDistributionEndToEnd:
    def test_distribute_persists_to_db(self, db_session):
        engine = DistributionEngine(db_session=db_session)
        call = SkillCall(
            call_id="call-001",
            skill_id="skill-001",
            caller_id="user-001",
            input_data={},
            revenue_usd=100.0,
        )

        record = engine.distribute(call)

        assert record.total_amount == 100.0
        assert record.platform_fee == 5.0
        assert record.ecosystem_fee == 25.0
        assert record.contributor_pool == 70.0

        # 验证 DB 持久化
        repo = DistributionRepository(db_session)
        models = repo.list_by_skill("skill-001")
        assert len(models) == 1
        assert models[0].total_amount == 100.0

    def test_ecosystem_breakdown_sums_correctly(self, db_session):
        engine = DistributionEngine(db_session=db_session)
        call = SkillCall(call_id="call-002", skill_id="skill-001", caller_id="user-001", input_data={}, revenue_usd=100.0)
        record = engine.distribute(call)

        total_ecosystem = sum(record.ecosystem_breakdown.values())
        # ecosystem_breakdown is a subset (25% * 25% = 6.25% of total), not the full ecosystem_fee
        assert total_ecosystem == pytest.approx(100.0 * 0.25 * 0.25, abs=1e-6)

    def test_secondary_distribution_sums_correctly(self, db_session):
        engine = DistributionEngine(db_session=db_session)
        call = SkillCall(call_id="call-003", skill_id="skill-001", caller_id="user-001", input_data={}, revenue_usd=100.0)
        record = engine.distribute(call)

        total_secondary = sum(record.secondary_distribution.values())
        assert total_secondary == pytest.approx(record.contributor_pool, abs=1e-6)

    def test_register_contributor_persists_to_db(self, db_session):
        engine = DistributionEngine(db_session=db_session)
        contributor = Contributor(
            contributor_id="contrib-001",
            name="Alice",
            historical_contribution=0.8,
            current_period_attribution=0.7,
            success_rate=0.95,
            governance_participation=0.6,
        )
        engine.register_contributor(contributor)

        repo = ContributorRepository(db_session)
        model = repo.get("contrib-001")
        assert model is not None
        assert model.name == "Alice"

    def test_calculate_weight(self, db_session):
        engine = DistributionEngine(db_session=db_session)
        contributor = Contributor(
            contributor_id="contrib-001",
            name="Alice",
            historical_contribution=1.0,
            current_period_attribution=1.0,
            success_rate=1.0,
            governance_participation=1.0,
        )
        weight = engine.calculate_weight(contributor)
        assert weight == 1.0

    def test_compute_payouts(self, db_session):
        engine = DistributionEngine(db_session=db_session)
        contributors = [
            Contributor("c1", "Alice", 0.8, 0.7, 0.9, 0.5),
            Contributor("c2", "Bob", 0.5, 0.6, 0.8, 0.4),
        ]
        payouts = engine.compute_payouts(contributors, 1000.0)

        assert len(payouts) == 2
        total_payout = sum(p.amount for p in payouts)
        assert total_payout == pytest.approx(1000.0, abs=1e-4)

    def test_compute_payouts_empty_returns_empty(self, db_session):
        engine = DistributionEngine(db_session=db_session)
        assert engine.compute_payouts([], 100.0) == []

    def test_compute_payouts_zero_weight_returns_empty(self, db_session):
        engine = DistributionEngine(db_session=db_session)
        contributors = [
            Contributor("c1", "Alice", 0.0, 0.0, 0.0, 0.0),
        ]
        assert engine.compute_payouts(contributors, 100.0) == []

    def test_settle_with_no_revenue_returns_none(self, db_session):
        engine = DistributionEngine(db_session=db_session)
        result = engine.settle(SettlementPeriod.DAILY)
        assert result is None

    def test_get_contributor_cache_then_db(self, db_session):
        engine = DistributionEngine(db_session=db_session)
        contributor = Contributor("c1", "Alice", 0.8, 0.7, 0.9, 0.5)
        engine.register_contributor(contributor)

        # 从缓存获取
        cached = engine.get_contributor("c1")
        assert cached is not None

        # 清除缓存，从 DB 获取
        engine._contributor_registry.clear()
        from_db = engine.get_contributor("c1")
        assert from_db is not None
        assert from_db.name == "Alice"

    def test_distribution_log_persists_and_loads(self, db_session):
        engine = DistributionEngine(db_session=db_session)
        call = SkillCall(call_id="call-log", skill_id="skill-001", caller_id="user-001", input_data={}, revenue_usd=50.0)
        engine.distribute(call)

        # 清除内存日志，从 DB 重新加载
        engine._distribution_log.clear()
        logs = engine.get_distribution_log()
        assert len(logs) == 1
        assert logs[0].call_id == "call-log"


# =============================================================================
# Test 4: Audit 链式验证
# =============================================================================

class TestAuditChain:
    def test_log_creates_signed_record(self, audit_logger):
        record = audit_logger.log(
            AuditEventType.SKILL_EXECUTED,
            actor_id="user-001",
            resource_id="skill-001",
            action="Execute skill",
            details={"input": "hello"},
        )
        assert record.event_type == AuditEventType.SKILL_EXECUTED
        assert record.signature != ""
        assert record.prev_hash == ""

    def test_chain_links_records(self, audit_logger):
        r1 = audit_logger.log(AuditEventType.SESSION_CREATED, "user-001", "session-001", "Create")
        r2 = audit_logger.log(AuditEventType.SKILL_EXECUTED, "user-001", "skill-001", "Execute")

        assert r2.prev_hash != ""
        assert r2.prev_hash == audit_logger._compute_record_hash(r1)

    def test_verify_chain_passes_for_valid_logs(self, audit_logger):
        audit_logger.log(AuditEventType.SESSION_CREATED, "user-001", "session-001", "Create")
        audit_logger.log(AuditEventType.SKILL_EXECUTED, "user-001", "skill-001", "Execute")
        audit_logger.log(AuditEventType.SETTLEMENT_SUBMITTED, "user-001", "settle-001", "Submit")

        assert audit_logger.verify_chain() is True

    def test_query_by_event_type(self, audit_logger):
        audit_logger.log(AuditEventType.SESSION_CREATED, "user-001", "session-001", "Create")
        audit_logger.log(AuditEventType.SKILL_EXECUTED, "user-001", "skill-001", "Execute")
        audit_logger.log(AuditEventType.SESSION_CREATED, "user-002", "session-002", "Create")

        results = audit_logger.query(event_type=AuditEventType.SESSION_CREATED)
        assert len(results) == 2

    def test_query_by_actor_id(self, audit_logger):
        audit_logger.log(AuditEventType.SKILL_EXECUTED, "user-001", "skill-001", "Execute")
        audit_logger.log(AuditEventType.SKILL_EXECUTED, "user-002", "skill-002", "Execute")

        results = audit_logger.query(actor_id="user-001")
        assert len(results) == 1
        assert results[0]["actor_id"] == "user-001"

    def test_sanitize_sensitive_fields(self, audit_logger):
        record = audit_logger.log(
            AuditEventType.AUTH_SUCCESS,
            "user-001",
            "auth-001",
            "Login",
            details={"password": "secret123", "api_key": "key-abc", "normal_field": "ok"},
        )
        assert record.details["password"] == "***REDACTED***"
        assert record.details["api_key"] == "***REDACTED***"
        assert record.details["normal_field"] == "ok"

    def test_export_returns_json(self, audit_logger):
        audit_logger.log(AuditEventType.SKILL_EXECUTED, "user-001", "skill-001", "Execute")
        exported = audit_logger.export()
        assert exported.startswith("[")
        assert "skill-001" in exported


# =============================================================================
# Test 5: DB 持久化验证
# =============================================================================

class TestDbPersistence:
    def test_skill_survives_session_recreate(self, db_session):
        kernel = SkillKernel(db_session=db_session)
        manifest = kernel.distill("https://github.com/alice/persist-skill")
        skill_id = manifest.id

        # 模拟新 session（清除缓存）
        kernel2 = SkillKernel(db_session=db_session)
        recovered = kernel2.get_skill(skill_id)
        assert recovered is not None
        assert recovered.name == "persist-skill"

    def test_session_survives_session_recreate(self, db_session):
        manager = SessionManager(db_session=db_session)
        session = manager.create_session("user-001", metadata={"key": "value"})
        sid = session.session_id

        # 模拟新 session（清除缓存）
        manager2 = SessionManager(db_session=db_session)
        recovered = manager2.get_session(sid)
        assert recovered is not None
        assert recovered.metadata == {"key": "value"}

    def test_distribution_survives_session_recreate(self, db_session):
        engine = DistributionEngine(db_session=db_session)
        call = SkillCall(call_id="call-persist", skill_id="skill-001", caller_id="user-001", input_data={}, revenue_usd=25.0)
        engine.distribute(call)

        # 模拟新 session（清除缓存）
        engine2 = DistributionEngine(db_session=db_session)
        logs = engine2.get_distribution_log()
        assert len(logs) == 1
        assert logs[0].total_amount == 25.0

    def test_contributor_survives_session_recreate(self, db_session):
        engine = DistributionEngine(db_session=db_session)
        contributor = Contributor("c-persist", "Bob", 0.5, 0.5, 0.5, 0.5)
        engine.register_contributor(contributor)

        engine2 = DistributionEngine(db_session=db_session)
        recovered = engine2.get_contributor("c-persist")
        assert recovered is not None
        assert recovered.name == "Bob"

    def test_multiple_models_in_same_db(self, db_session):
        kernel = SkillKernel(db_session=db_session)
        manager = SessionManager(db_session=db_session)
        engine = DistributionEngine(db_session=db_session)

        manifest = kernel.distill("https://github.com/alice/multi-skill")
        session = manager.create_session("user-001")
        call = SkillCall(call_id="call-multi", skill_id=manifest.id, caller_id="user-001", input_data={}, revenue_usd=10.0)
        engine.distribute(call)

        # 验证所有模型都在同一个 DB 中
        assert db_session.query(SkillModel).count() == 1
        assert db_session.query(SessionModel).count() == 1
        assert db_session.query(DistributionRecordModel).count() == 1

    def test_delete_contributor_from_db(self, db_session):
        engine = DistributionEngine(db_session=db_session)
        contributor = Contributor("c-del", "ToDelete", 0.1, 0.1, 0.1, 0.1)
        engine.register_contributor(contributor)

        repo = ContributorRepository(db_session)
        assert repo.get("c-del") is not None

        model = repo.get("c-del")
        db_session.delete(model)
        db_session.commit()
        assert repo.get("c-del") is None
