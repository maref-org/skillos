"""Tests for skillos.governance — Governance Layer (L6)

覆盖:
  - DAOGovernance: 提案、投票、执行
  - SmartContractEngine: 合约部署、执行
  - ComplianceAuditor: 合规审计
"""

import pytest

governance = pytest.importorskip("skillos.governance")

from skillos.governance.compliance import (
    AuditStatus,
    ComplianceAuditor,
    ComplianceReport,
    DataComplianceReport,
    SecurityAuditReport,
)
from skillos.governance.contracts import (
    ContractStatus,
    ContractTrigger,
    ContractType,
    ExecutionResult,
    SmartContractEngine,
)
from skillos.governance.dao import (
    DAOGovernance,
    ProposalStatus,
    ProposalType,
    VoteType,
)

# ---------------------------------------------------------------------------
# DAOGovernance tests
# ---------------------------------------------------------------------------


class TestDAOGovernance:
    @pytest.fixture
    def dao(self, db_session):
        return DAOGovernance(db_session=db_session)

    @pytest.mark.asyncio
    async def test_create_proposal(self, dao):
        proposal_id = await dao.create_proposal(
            proposer_id="user-001",
            title="Test Proposal",
            description="A test proposal",
            proposal_type=ProposalType.PARAMETER_CHANGE,
            parameters={"key": "value"},
        )
        assert proposal_id
        proposal = await dao.get_proposal(proposal_id)
        assert proposal is not None
        assert proposal.title == "Test Proposal"
        assert proposal.status == ProposalStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_vote(self, dao):
        proposal_id = await dao.create_proposal(
            proposer_id="user-001",
            title="Test Proposal",
            description="A test proposal",
            proposal_type=ProposalType.PARAMETER_CHANGE,
            parameters={},
        )
        await dao.vote(proposal_id, "voter-001", VoteType.FOR, 10.0)
        proposal = await dao.get_proposal(proposal_id)
        assert proposal.vote_for == 10.0

    @pytest.mark.asyncio
    async def test_vote_duplicate(self, dao):
        proposal_id = await dao.create_proposal(
            proposer_id="user-001",
            title="Test Proposal",
            description="A test proposal",
            proposal_type=ProposalType.PARAMETER_CHANGE,
            parameters={},
        )
        await dao.vote(proposal_id, "voter-001", VoteType.FOR, 10.0)
        with pytest.raises(ValueError, match="Already voted"):
            await dao.vote(proposal_id, "voter-001", VoteType.FOR, 5.0)

    @pytest.mark.asyncio
    async def test_execute_proposal_passed(self, dao):
        proposal_id = await dao.create_proposal(
            proposer_id="user-001",
            title="Test Proposal",
            description="A test proposal",
            proposal_type=ProposalType.PARAMETER_CHANGE,
            parameters={},
        )
        await dao.vote(proposal_id, "voter-001", VoteType.FOR, 10.0)
        await dao.vote(proposal_id, "voter-002", VoteType.AGAINST, 5.0)
        result = await dao.execute_proposal(proposal_id)
        assert result.status == ProposalStatus.EXECUTED

    @pytest.mark.asyncio
    async def test_execute_proposal_rejected(self, dao):
        proposal_id = await dao.create_proposal(
            proposer_id="user-001",
            title="Test Proposal",
            description="A test proposal",
            proposal_type=ProposalType.PARAMETER_CHANGE,
            parameters={},
        )
        await dao.vote(proposal_id, "voter-001", VoteType.AGAINST, 10.0)
        await dao.vote(proposal_id, "voter-002", VoteType.FOR, 5.0)
        result = await dao.execute_proposal(proposal_id)
        assert result.status == ProposalStatus.REJECTED

    @pytest.mark.asyncio
    async def test_list_proposals(self, dao):
        await dao.create_proposal(
            proposer_id="user-001",
            title="Proposal 1",
            description="First",
            proposal_type=ProposalType.PARAMETER_CHANGE,
            parameters={},
        )
        await dao.create_proposal(
            proposer_id="user-002",
            title="Proposal 2",
            description="Second",
            proposal_type=ProposalType.FUND_ALLOCATION,
            parameters={},
        )
        proposals = await dao.list_proposals()
        assert len(proposals) == 2

    @pytest.mark.asyncio
    async def test_cancel_proposal(self, dao):
        proposal_id = await dao.create_proposal(
            proposer_id="user-001",
            title="Test Proposal",
            description="A test proposal",
            proposal_type=ProposalType.PARAMETER_CHANGE,
            parameters={},
        )
        await dao.cancel_proposal(proposal_id, "user-001")
        proposal = await dao.get_proposal(proposal_id)
        assert proposal.status == ProposalStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_proposal_unauthorized(self, dao):
        proposal_id = await dao.create_proposal(
            proposer_id="user-001",
            title="Test Proposal",
            description="A test proposal",
            proposal_type=ProposalType.PARAMETER_CHANGE,
            parameters={},
        )
        with pytest.raises(ValueError, match="Only proposer can cancel"):
            await dao.cancel_proposal(proposal_id, "user-002")


# ---------------------------------------------------------------------------
# SmartContractEngine tests
# ---------------------------------------------------------------------------


class TestSmartContractEngine:
    @pytest.fixture
    def engine(self, db_session):
        return SmartContractEngine(db_session=db_session)

    @pytest.mark.asyncio
    async def test_deploy_contract(self, engine):
        contract_id = await engine.deploy_contract(
            ContractType.FUND_ALLOCATION,
            {"allocations": {"a": 0.5, "b": 0.5}},
        )
        assert contract_id
        state = await engine.get_contract_state(contract_id)
        assert state.contract_type == ContractType.FUND_ALLOCATION
        assert state.status == ContractStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_execute_contract(self, engine):
        contract_id = await engine.deploy_contract(
            ContractType.PARAMETER_UPDATE,
            {"key": "fee", "value": 0.05},
        )
        result = await engine.execute_contract(contract_id, ContractTrigger.MANUAL)
        assert isinstance(result, ExecutionResult)
        assert result.success
        assert result.output["updated"]["fee"] == 0.05

    @pytest.mark.asyncio
    async def test_pause_contract(self, engine):
        contract_id = await engine.deploy_contract(
            ContractType.FUND_ALLOCATION,
            {"allocations": {}},
        )
        await engine.pause_contract(contract_id)
        state = await engine.get_contract_state(contract_id)
        assert state.status == ContractStatus.PAUSED

    @pytest.mark.asyncio
    async def test_terminate_contract(self, engine):
        contract_id = await engine.deploy_contract(
            ContractType.FUND_ALLOCATION,
            {"allocations": {}},
        )
        await engine.terminate_contract(contract_id)
        state = await engine.get_contract_state(contract_id)
        assert state.status == ContractStatus.TERMINATED

    @pytest.mark.asyncio
    async def test_execute_terminated_contract(self, engine):
        contract_id = await engine.deploy_contract(
            ContractType.FUND_ALLOCATION,
            {"allocations": {}},
        )
        await engine.terminate_contract(contract_id)
        with pytest.raises(ValueError, match="Contract terminated"):
            await engine.execute_contract(contract_id, ContractTrigger.MANUAL)

    @pytest.mark.asyncio
    async def test_register_custom_handler(self, engine):
        def custom_handler(params):
            return {"custom": True, "params": params}

        engine.register_handler(ContractType.EMERGENCY_PAUSE, custom_handler)
        contract_id = await engine.deploy_contract(
            ContractType.EMERGENCY_PAUSE,
            {"reason": "test"},
        )
        result = await engine.execute_contract(contract_id, ContractTrigger.EVENT_BASED)
        assert result.success
        assert result.output["custom"] is True


# ---------------------------------------------------------------------------
# ComplianceAuditor tests
# ---------------------------------------------------------------------------


class TestComplianceAuditor:
    @pytest.fixture
    def auditor(self, db_session):
        return ComplianceAuditor(db_session=db_session)

    @pytest.mark.asyncio
    async def test_run_security_audit(self, auditor):
        report = await auditor.run_security_audit()
        assert isinstance(report, SecurityAuditReport)
        assert report.status in (AuditStatus.PASSED, AuditStatus.WARNING)
        assert "tls_1_3" in report.checks

    @pytest.mark.asyncio
    async def test_check_data_compliance(self, auditor):
        report = await auditor.check_data_compliance()
        assert isinstance(report, DataComplianceReport)
        assert report.status in (AuditStatus.PASSED, AuditStatus.WARNING)
        assert "user_identity" in report.data_classes

    @pytest.mark.asyncio
    async def test_generate_compliance_report(self, auditor):

        report = await auditor.generate_compliance_report("2026-05")
        assert isinstance(report, ComplianceReport)
        assert report.period == "2026-05"
        assert report.security is not None
        assert report.data is not None
        assert report.overall_status in (AuditStatus.PASSED, AuditStatus.WARNING)
