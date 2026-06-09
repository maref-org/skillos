"""Performance tests — 基准与负载测试

Phase 4.4: 性能测试
覆盖场景：
  1. SkillKernel 基准（蒸馏、NFT 铸造、查询）
  2. SessionManager 基准（创建、添加 item、查询）
  3. DistributionEngine 基准（分配计算、Payout 计算）
  4. AuditLogger 基准（日志写入、链式校验）
  5. DB 批量操作负载测试
"""

import tempfile
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from skillos.audit import AuditEventType, AuditLogger
from skillos.db.engine import Base
from skillos.distribution.engine import DistributionEngine
from skillos.kernel.session_manager import SessionManager
from skillos.kernel.skill_kernel import SkillKernel
from skillos.types import Contributor, SkillCall


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


# =============================================================================
# SkillKernel Performance
# =============================================================================


class TestSkillKernelPerformance:
    def test_distill_benchmark(self, db_session):
        """蒸馏 100 个 Skill 的耗时基准"""
        kernel = SkillKernel(db_session=db_session)
        start = time.perf_counter()

        for i in range(100):
            kernel.distill(f"https://github.com/user/skill-{i}")

        elapsed = time.perf_counter() - start
        assert elapsed < 5.0  # 5 秒内完成 100 次蒸馏
        print(f"\nDistill 100 skills: {elapsed:.3f}s")

    def test_get_skill_benchmark(self, db_session):
        """查询 1000 次已缓存 Skill 的耗时"""
        kernel = SkillKernel(db_session=db_session)
        manifest = kernel.distill("https://github.com/user/benchmark-skill")

        start = time.perf_counter()
        for _ in range(1000):
            kernel.get_skill(manifest.id)
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0  # 1 秒内完成 1000 次缓存查询
        print(f"\nGet skill (cached) 1000x: {elapsed:.3f}s")

    def test_list_skills_benchmark(self, db_session):
        """列出 100 个 Skill 的耗时"""
        kernel = SkillKernel(db_session=db_session)
        for i in range(100):
            kernel.distill(f"https://github.com/user/skill-{i}")

        start = time.perf_counter()
        skills = kernel.list_skills()
        elapsed = time.perf_counter() - start

        assert len(skills) == 100
        assert elapsed < 2.0
        print(f"\nList 100 skills: {elapsed:.3f}s")


# =============================================================================
# SessionManager Performance
# =============================================================================


class TestSessionManagerPerformance:
    def test_create_session_benchmark(self, db_session):
        """创建 100 个会话的耗时"""
        manager = SessionManager(db_session=db_session)
        start = time.perf_counter()

        for i in range(100):
            manager.create_session(f"user-{i % 10}")

        elapsed = time.perf_counter() - start
        assert elapsed < 5.0
        print(f"\nCreate 100 sessions: {elapsed:.3f}s")

    def test_add_item_benchmark(self, db_session):
        """向单个会话添加 500 个 item 的耗时"""
        manager = SessionManager(db_session=db_session)
        session = manager.create_session("user-001")

        start = time.perf_counter()
        for i in range(500):
            manager.add_item(session.session_id, {"role": "user", "content": f"msg-{i}"})
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0
        assert len(session.items) == 500
        print(f"\nAdd 500 items: {elapsed:.3f}s")

    def test_list_sessions_benchmark(self, db_session):
        """列出 100 个会话的耗时"""
        manager = SessionManager(db_session=db_session)
        for i in range(100):
            manager.create_session(f"user-{i}")

        start = time.perf_counter()
        sessions = manager.list_sessions()
        elapsed = time.perf_counter() - start

        assert len(sessions) == 100
        assert elapsed < 2.0
        print(f"\nList 100 sessions: {elapsed:.3f}s")


# =============================================================================
# DistributionEngine Performance
# =============================================================================


class TestDistributionPerformance:
    def test_distribute_benchmark(self, db_session):
        """1000 次收入分配的耗时"""
        engine = DistributionEngine(db_session=db_session)
        start = time.perf_counter()

        for i in range(1000):
            call = SkillCall(
                call_id=f"call-{i}",
                skill_id="skill-001",
                caller_id="user-001",
                input_data={},
                revenue_usd=1.0,
            )
            engine.distribute(call)

        elapsed = time.perf_counter() - start
        assert elapsed < 10.0
        print(f"\nDistribute 1000 calls: {elapsed:.3f}s")

    def test_compute_payouts_benchmark(self, db_session):
        """计算 100 个贡献者的 payout 耗时"""
        engine = DistributionEngine(db_session=db_session)
        contributors = [Contributor(f"c-{i}", f"Name-{i}", 0.5, 0.5, 0.8, 0.3) for i in range(100)]

        start = time.perf_counter()
        payouts = engine.compute_payouts(contributors, 10000.0)
        elapsed = time.perf_counter() - start

        assert len(payouts) == 100
        assert elapsed < 1.0
        print(f"\nCompute payouts for 100 contributors: {elapsed:.3f}s")

    def test_calculate_weight_benchmark(self, db_session):
        """计算 10000 次权重耗时"""
        engine = DistributionEngine(db_session=db_session)
        contributor = Contributor("c1", "Alice", 0.8, 0.7, 0.9, 0.5)

        start = time.perf_counter()
        for _ in range(10000):
            engine.calculate_weight(contributor)
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0
        print(f"\nCalculate weight 10000x: {elapsed:.3f}s")


# =============================================================================
# AuditLogger Performance
# =============================================================================


class TestAuditPerformance:
    def test_log_benchmark(self):
        """写入 500 条审计日志的耗时"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(log_dir=tmpdir, secret_key="perf-test")
            start = time.perf_counter()

            for i in range(500):
                logger.log(
                    AuditEventType.SKILL_EXECUTED,
                    f"user-{i % 100}",
                    f"skill-{i % 50}",
                    "Execute",
                    details={"index": i},
                )

            elapsed = time.perf_counter() - start
            assert elapsed < 5.0
            print(f"\nLog 500 audit records: {elapsed:.3f}s")

    def test_verify_chain_benchmark(self):
        """校验 500 条日志链的耗时"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(log_dir=tmpdir, secret_key="perf-test")
            for i in range(500):
                logger.log(AuditEventType.SKILL_EXECUTED, "user-001", "skill-001", "Execute")

            start = time.perf_counter()
            result = logger.verify_chain()
            elapsed = time.perf_counter() - start

            assert result is True
            assert elapsed < 2.0
            print(f"\nVerify chain of 500 records: {elapsed:.3f}s")

    def test_query_benchmark(self):
        """查询 500 条日志中的特定类型耗时"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(log_dir=tmpdir, secret_key="perf-test")
            for i in range(500):
                event = AuditEventType.SKILL_EXECUTED if i % 2 == 0 else AuditEventType.SESSION_CREATED
                logger.log(event, "user-001", "resource-001", "Action")

            start = time.perf_counter()
            results = logger.query(event_type=AuditEventType.SKILL_EXECUTED, limit=500)
            elapsed = time.perf_counter() - start

            assert len(results) == 250
            assert elapsed < 1.0
            print(f"\nQuery 250/500 records: {elapsed:.3f}s")


# =============================================================================
# DB Bulk Operations
# =============================================================================


class TestDbBulkPerformance:
    def test_bulk_skill_insert(self, db_session):
        """批量插入 100 个 Skill 并查询"""
        kernel = SkillKernel(db_session=db_session)
        start = time.perf_counter()

        for i in range(100):
            kernel.distill(f"https://github.com/user/bulk-skill-{i}")

        elapsed_insert = time.perf_counter() - start

        start = time.perf_counter()
        skills = kernel.list_skills()
        elapsed_query = time.perf_counter() - start

        assert len(skills) == 100
        assert elapsed_insert < 5.0
        assert elapsed_query < 2.0
        print(f"\nBulk insert 100 skills: {elapsed_insert:.3f}s, query: {elapsed_query:.3f}s")

    def test_bulk_session_insert(self, db_session):
        """批量插入 100 个 Session 并查询"""
        manager = SessionManager(db_session=db_session)
        start = time.perf_counter()

        for i in range(100):
            manager.create_session(f"user-{i}")

        elapsed_insert = time.perf_counter() - start

        start = time.perf_counter()
        sessions = manager.list_sessions()
        elapsed_query = time.perf_counter() - start

        assert len(sessions) == 100
        assert elapsed_insert < 5.0
        assert elapsed_query < 2.0
        print(f"\nBulk insert 100 sessions: {elapsed_insert:.3f}s, query: {elapsed_query:.3f}s")

    def test_bulk_distribution_insert(self, db_session):
        """批量插入 500 条分配记录并查询"""
        engine = DistributionEngine(db_session=db_session)
        start = time.perf_counter()

        for i in range(500):
            call = SkillCall(
                call_id=f"bulk-{i}",
                skill_id="skill-001",
                caller_id="user-001",
                input_data={},
                revenue_usd=1.0,
            )
            engine.distribute(call)

        elapsed_insert = time.perf_counter() - start

        start = time.perf_counter()
        logs = engine.get_distribution_log()
        elapsed_query = time.perf_counter() - start

        assert len(logs) == 500
        assert elapsed_insert < 10.0
        assert elapsed_query < 3.0
        print(f"\nBulk insert 500 distributions: {elapsed_insert:.3f}s, query: {elapsed_query:.3f}s")
