"""Tests for skillos.kernel.skill_kernel - Distillation, NFT, ToolChain, Execution"""

import asyncio
import hashlib
import time

import pytest

from skillos.kernel.skill_kernel import SkillKernel, SkillNFT, ToolChain
from skillos._types import SkillCall, SkillManifest, SkillStatus


class TestToolChain:
    def test_basic_fields(self):
        chain = ToolChain(
            skill_id="sk-001",
            tools=[{"name": "executor"}],
            mcp_connectors=["mcp://sk-001"],
            a2a_adapters=["a2a://sk-001"],
        )
        assert chain.skill_id == "sk-001"
        assert len(chain.tools) == 1

    def test_execution_env_default(self):
        chain = ToolChain(
            skill_id="sk-001",
            tools=[],
            mcp_connectors=[],
            a2a_adapters=[],
        )
        assert chain.execution_env == "wasm_sandbox"

    def test_custom_execution_env(self):
        chain = ToolChain(
            skill_id="sk-001",
            tools=[],
            mcp_connectors=[],
            a2a_adapters=[],
            execution_env="docker",
        )
        assert chain.execution_env == "docker"


class TestSkillNFT:
    def test_basic_fields(self):
        nft = SkillNFT(
            skill_id="sk-001",
            token_id="nft-sk-001",
            owner="alice",
            metadata_hash="abc123",
        )
        assert nft.skill_id == "sk-001"
        assert nft.owner == "alice"

    def test_minted_at_timestamp(self):
        before = time.time()
        nft = SkillNFT(
            skill_id="sk-001",
            token_id="nft-sk-001",
            owner="alice",
            metadata_hash="abc123",
        )
        after = time.time()
        assert before <= nft.minted_at <= after


class TestSkillKernelInit:
    def test_default_init(self):
        kernel = SkillKernel()
        assert kernel.registry is None
        assert kernel._skill_cache == {}
        assert kernel._nft_records == []
        assert kernel._execution_log == []

    def test_init_with_registry(self, mock_registry):
        kernel = SkillKernel(registry=mock_registry)
        assert kernel.registry is mock_registry


class TestDistill:
    def test_distill_returns_manifest(self):
        kernel = SkillKernel()
        manifest = kernel.distill("https://github.com/user/my-skill")
        assert isinstance(manifest, SkillManifest)

    def test_distill_generates_skill_id(self):
        kernel = SkillKernel()
        manifest = kernel.distill("https://github.com/user/my-skill")
        assert manifest.id.startswith("skill-")
        assert len(manifest.id) == len("skill-") + 12

    def test_distill_id_is_deterministic(self):
        kernel = SkillKernel()
        m1 = kernel.distill("https://github.com/user/my-skill")
        m2 = kernel.distill("https://github.com/user/my-skill")
        assert m1.id == m2.id

    def test_distill_infers_name(self):
        kernel = SkillKernel()
        manifest = kernel.distill("https://github.com/user/my-awesome-skill")
        assert manifest.name == "my-awesome-skill"

    def test_distill_infers_author_github(self):
        kernel = SkillKernel()
        manifest = kernel.distill("https://github.com/openhuman/skill-ai")
        assert manifest.author == "openhuman"

    def test_distill_author_anonymous_non_github(self):
        kernel = SkillKernel()
        manifest = kernel.distill("https://gitlab.com/user/skill")
        assert manifest.author == "anonymous"

    def test_distill_version_default(self):
        kernel = SkillKernel()
        manifest = kernel.distill("https://github.com/user/skill")
        assert manifest.version == "1.0.0"

    def test_distill_status_draft(self):
        kernel = SkillKernel()
        manifest = kernel.distill("https://github.com/user/skill")
        assert manifest.status == SkillStatus.DRAFT

    def test_distill_entry_point_default(self):
        kernel = SkillKernel()
        manifest = kernel.distill("https://github.com/user/skill")
        assert manifest.entry_point == "main.py"

    def test_distill_dependencies(self):
        kernel = SkillKernel()
        manifest = kernel.distill("https://github.com/user/skill")
        assert manifest.dependencies == ["python>=3.11"]

    def test_distill_metadata_contains_source(self):
        kernel = SkillKernel()
        url = "https://github.com/user/my-skill"
        manifest = kernel.distill(url)
        assert manifest.metadata["source_repo"] == url

    def test_distill_caches_manifest(self):
        kernel = SkillKernel()
        manifest = kernel.distill("https://github.com/user/skill")
        cached = kernel.get_skill(manifest.id)
        assert cached is manifest

    def test_distill_description_format(self):
        kernel = SkillKernel()
        url = "https://github.com/user/skill"
        manifest = kernel.distill(url)
        assert manifest.description == f"Auto-distilled from {url}"

    def test_distill_different_urls_different_ids(self):
        kernel = SkillKernel()
        m1 = kernel.distill("https://github.com/user/skill-a")
        m2 = kernel.distill("https://github.com/user/skill-b")
        assert m1.id != m2.id


class TestMintNft:
    def test_mint_returns_nft(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        assert isinstance(nft, SkillNFT)

    def test_mint_nft_skill_id(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        assert nft.skill_id == skill_manifest.id

    def test_mint_nft_token_id_format(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        assert nft.token_id == f"nft-{skill_manifest.id}"

    def test_mint_nft_owner_is_author(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        assert nft.owner == skill_manifest.author

    def test_mint_nft_metadata_hash(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        expected_content = f"{skill_manifest.id}:{skill_manifest.version}:{skill_manifest.author}"
        expected_hash = hashlib.sha256(expected_content.encode()).hexdigest()
        assert nft.metadata_hash == expected_hash

    def test_mint_nft_records_to_log(self, skill_manifest):
        kernel = SkillKernel()
        kernel.mint_nft(skill_manifest)
        assert len(kernel._nft_records) == 1
        assert kernel._nft_records[0].skill_id == skill_manifest.id

    def test_mint_multiple_nfts(self, skill_manifest):
        kernel = SkillKernel()
        m2 = SkillManifest(
            id="sk-002",
            name="skill-2",
            version="1.0.0",
            author="bob",
            description="second skill",
        )
        kernel.mint_nft(skill_manifest)
        kernel.mint_nft(m2)
        assert len(kernel._nft_records) == 2

    def test_mint_nft_timestamp(self, skill_manifest):
        kernel = SkillKernel()
        before = time.time()
        nft = kernel.mint_nft(skill_manifest)
        after = time.time()
        assert before <= nft.minted_at <= after


class TestAssembleTools:
    def test_assemble_returns_toolchain(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        kernel._skill_cache[skill_manifest.id] = skill_manifest
        chain = kernel.assemble_tools(nft)
        assert isinstance(chain, ToolChain)

    def test_assemble_tools_skill_id(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        kernel._skill_cache[skill_manifest.id] = skill_manifest
        chain = kernel.assemble_tools(nft)
        assert chain.skill_id == skill_manifest.id

    def test_assemble_tools_default_executor(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        kernel._skill_cache[skill_manifest.id] = skill_manifest
        chain = kernel.assemble_tools(nft)
        assert len(chain.tools) == 1
        assert chain.tools[0]["name"] == "default_executor"
        assert chain.tools[0]["type"] == "python"
        assert chain.tools[0]["entry"] == skill_manifest.entry_point

    def test_assemble_tools_mcp_connector(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        kernel._skill_cache[skill_manifest.id] = skill_manifest
        chain = kernel.assemble_tools(nft)
        assert chain.mcp_connectors == [f"mcp://{skill_manifest.id}"]

    def test_assemble_tools_a2a_adapter(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        kernel._skill_cache[skill_manifest.id] = skill_manifest
        chain = kernel.assemble_tools(nft)
        assert chain.a2a_adapters == [f"a2a://{skill_manifest.id}"]

    def test_assemble_tools_raises_when_skill_not_found(self):
        kernel = SkillKernel()
        nft = SkillNFT(
            skill_id="nonexistent",
            token_id="nft-x",
            owner="alice",
            metadata_hash="hash",
        )
        with pytest.raises(ValueError, match="not found in cache"):
            kernel.assemble_tools(nft)


class TestExecute:
    def test_execute_returns_result(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        kernel._skill_cache[skill_manifest.id] = skill_manifest
        chain = kernel.assemble_tools(nft)
        result = asyncio.run(kernel.execute(chain, {"input": "test"}))
        assert result["status"] == "completed"

    def test_execute_contains_skill_id(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        kernel._skill_cache[skill_manifest.id] = skill_manifest
        chain = kernel.assemble_tools(nft)
        result = asyncio.run(kernel.execute(chain, {}))
        assert result["skill_id"] == skill_manifest.id

    def test_execute_output_message(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        kernel._skill_cache[skill_manifest.id] = skill_manifest
        chain = kernel.assemble_tools(nft)
        result = asyncio.run(kernel.execute(chain, {}))
        assert "executed successfully" in result["output"]["message"]

    def test_execute_logs_to_execution_log(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        kernel._skill_cache[skill_manifest.id] = skill_manifest
        chain = kernel.assemble_tools(nft)
        asyncio.run(kernel.execute(chain, {}))
        assert len(kernel._execution_log) == 1
        assert kernel._execution_log[0]["skill_id"] == skill_manifest.id
        assert kernel._execution_log[0]["status"] == "completed"

    def test_execute_latency_recorded(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        kernel._skill_cache[skill_manifest.id] = skill_manifest
        chain = kernel.assemble_tools(nft)
        asyncio.run(kernel.execute(chain, {}))
        log_entry = kernel._execution_log[0]
        assert "latency_ms" in log_entry
        assert isinstance(log_entry["latency_ms"], float)

    def test_execute_timestamp_recorded(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        kernel._skill_cache[skill_manifest.id] = skill_manifest
        chain = kernel.assemble_tools(nft)
        before = time.time()
        asyncio.run(kernel.execute(chain, {}))
        after = time.time()
        log_entry = kernel._execution_log[0]
        assert before <= log_entry["timestamp"] <= after

    def test_multiple_executions(self, skill_manifest):
        kernel = SkillKernel()
        nft = kernel.mint_nft(skill_manifest)
        kernel._skill_cache[skill_manifest.id] = skill_manifest
        chain = kernel.assemble_tools(nft)
        asyncio.run(kernel.execute(chain, {}))
        asyncio.run(kernel.execute(chain, {}))
        assert len(kernel._execution_log) == 2


class TestGetSkill:
    def test_get_skill_after_distill(self):
        kernel = SkillKernel()
        manifest = kernel.distill("https://github.com/user/test-skill")
        result = kernel.get_skill(manifest.id)
        assert result is manifest

    def test_get_nonexistent_skill(self):
        kernel = SkillKernel()
        result = kernel.get_skill("nonexistent")
        assert result is None


class TestListSkills:
    def test_list_all_skills(self):
        kernel = SkillKernel()
        kernel.distill("https://github.com/user/skill-a")
        kernel.distill("https://github.com/user/skill-b")
        skills = kernel.list_skills()
        assert len(skills) == 2

    def test_list_skills_empty(self):
        kernel = SkillKernel()
        assert kernel.list_skills() == []

    def test_list_skills_filter_by_status(self):
        kernel = SkillKernel()
        m1 = kernel.distill("https://github.com/user/skill-a")
        kernel.distill("https://github.com/user/skill-b")
        kernel.update_status(m1.id, SkillStatus.PUBLISHED)
        published = kernel.list_skills(status=SkillStatus.PUBLISHED)
        assert len(published) == 1
        assert published[0].id == m1.id

    def test_list_skills_filter_no_match(self):
        kernel = SkillKernel()
        kernel.distill("https://github.com/user/skill-a")
        deprecated = kernel.list_skills(status=SkillStatus.DEPRECATED)
        assert len(deprecated) == 0


class TestUpdateStatus:
    def test_update_status_success(self):
        kernel = SkillKernel()
        manifest = kernel.distill("https://github.com/user/skill")
        result = kernel.update_status(manifest.id, SkillStatus.PUBLISHED)
        assert result is True
        assert manifest.status == SkillStatus.PUBLISHED

    def test_update_status_nonexistent(self):
        kernel = SkillKernel()
        result = kernel.update_status("nonexistent", SkillStatus.PUBLISHED)
        assert result is False

    def test_update_status_to_deprecated(self):
        kernel = SkillKernel()
        manifest = kernel.distill("https://github.com/user/skill")
        kernel.update_status(manifest.id, SkillStatus.DEPRECATED)
        assert manifest.status == SkillStatus.DEPRECATED

    def test_update_status_to_suspended(self):
        kernel = SkillKernel()
        manifest = kernel.distill("https://github.com/user/skill")
        kernel.update_status(manifest.id, SkillStatus.SUSPENDED)
        assert manifest.status == SkillStatus.SUSPENDED


class TestRegisterCall:
    def test_register_call(self, skill_call):
        kernel = SkillKernel()
        kernel.register_call(skill_call)
        assert skill_call.status == "completed"

    def test_register_call_logged(self, skill_call):
        kernel = SkillKernel()
        kernel.register_call(skill_call)
        log_entries = [e for e in kernel._execution_log if e.get("call_id") == skill_call.call_id]
        assert len(log_entries) == 1

    def test_register_call_contains_revenue(self):
        call = SkillCall(
            skill_id="sk-001",
            caller_id="caller-001",
            input_data={},
            revenue_usd=0.05,
        )
        kernel = SkillKernel()
        kernel.register_call(call)
        log_entry = [e for e in kernel._execution_log if e.get("call_id") == call.call_id][0]
        assert log_entry["revenue_usd"] == 0.05

    def test_register_call_timestamp(self):
        call = SkillCall(
            skill_id="sk-001",
            caller_id="caller-001",
            input_data={},
        )
        kernel = SkillKernel()
        kernel.register_call(call)
        log_entry = [e for e in kernel._execution_log if e.get("call_id") == call.call_id][0]
        assert log_entry["timestamp"] == call.timestamp


class TestInferName:
    def test_infer_name_from_github(self):
        name = SkillKernel._infer_name("https://github.com/user/my-skill")
        assert name == "my-skill"

    def test_infer_name_with_trailing_slash(self):
        name = SkillKernel._infer_name("https://github.com/user/my-skill/")
        assert name == "my-skill"

    def test_infer_name_minimal(self):
        name = SkillKernel._infer_name("my-skill")
        assert name == "my-skill"

    def test_infer_name_empty(self):
        name = SkillKernel._infer_name("")
        assert name == ""

    def test_infer_name_single_slash(self):
        name = SkillKernel._infer_name("/")
        assert name == ""


class TestInferAuthor:
    def test_infer_author_from_github(self):
        author = SkillKernel._infer_author("https://github.com/openhuman/skill")
        assert author == "openhuman"

    def test_infer_author_non_github(self):
        author = SkillKernel._infer_author("https://gitlab.com/user/skill")
        assert author == "anonymous"

    def test_infer_author_minimal(self):
        author = SkillKernel._infer_author("my-skill")
        assert author == "anonymous"

    def test_infer_author_github_com_in_path(self):
        author = SkillKernel._infer_author("https://proxy.com/github.com/user/skill")
        assert author == "user"
