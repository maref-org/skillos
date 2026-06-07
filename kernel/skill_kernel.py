#!/usr/bin/env python3
"""Skill Kernel — 技能生命周期管理

职责：
  - Skill 蒸馏（从 GitHub 仓库提取功能）
  - Skill NFT 铸造（ERC-721 确权）
  - 工具链组装（MCP Connector + A2A Adapter）
  - Skill 执行

流水线：
  GitHub 仓库 → 技能蒸馏器 → Skill NFT → 工具链组装 → 执行环境
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from skillos._types import SkillCall, SkillManifest, SkillStatus
from skillos.kernel.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ToolChain:
    skill_id: str
    tools: list[dict[str, Any]]
    mcp_connectors: list[str]
    a2a_adapters: list[str]
    execution_env: str = "wasm_sandbox"


@dataclass
class SkillNFT:
    skill_id: str
    token_id: str
    owner: str
    metadata_hash: str
    minted_at: float = field(default_factory=time.time)


class SkillKernel:
    """技能内核 — Skill 生命周期管理"""

    def __init__(self, registry: Any | None = None):
        self.registry = registry
        self._skill_cache: dict[str, SkillManifest] = {}
        self._nft_records: list[SkillNFT] = []
        self._execution_log: list[dict[str, Any]] = []

    def distill(self, repo_url: str) -> SkillManifest:
        """从 GitHub 仓库蒸馏 Skill"""
        logger.info("Distilling skill from: %s", repo_url)

        repo_hash = hashlib.sha256(repo_url.encode()).hexdigest()[:12]
        skill_id = f"skill-{repo_hash}"

        manifest = SkillManifest(
            id=skill_id,
            name=self._infer_name(repo_url),
            version="1.0.0",
            author=self._infer_author(repo_url),
            description=f"Auto-distilled from {repo_url}",
            entry_point="main.py",
            dependencies=["python>=3.11"],
            status=SkillStatus.DRAFT,
            metadata={"source_repo": repo_url},
        )

        self._skill_cache[skill_id] = manifest
        logger.info("Skill distilled: %s", skill_id)
        return manifest

    def mint_nft(self, manifest: SkillManifest) -> SkillNFT:
        """铸造 Skill NFT（ERC-721）"""
        metadata_content = f"{manifest.id}:{manifest.version}:{manifest.author}"
        metadata_hash = hashlib.sha256(metadata_content.encode()).hexdigest()

        nft = SkillNFT(
            skill_id=manifest.id,
            token_id=f"nft-{manifest.id}",
            owner=manifest.author,
            metadata_hash=metadata_hash,
        )

        self._nft_records.append(nft)
        logger.info("Skill NFT minted: %s for %s", nft.token_id, nft.owner)
        return nft

    def assemble_tools(self, nft: SkillNFT) -> ToolChain:
        """组装工具链（MCP Connector + A2A Adapter）"""
        skill = self._skill_cache.get(nft.skill_id)
        if skill is None:
            raise ValueError(f"Skill {nft.skill_id} not found in cache")

        tools = [
            {"name": "default_executor", "type": "python", "entry": skill.entry_point},
        ]

        return ToolChain(
            skill_id=nft.skill_id,
            tools=tools,
            mcp_connectors=[f"http://localhost:8000/mcp/v1/{nft.skill_id}"],
            a2a_adapters=[f"a2a://{nft.skill_id}"],
        )

    async def execute(self, tool_chain: ToolChain, input_data: dict[str, Any]) -> dict[str, Any]:
        """执行 Skill"""
        start = time.monotonic()
        logger.info("Executing skill: %s with input: %s", tool_chain.skill_id, input_data)

        result = {
            "skill_id": tool_chain.skill_id,
            "status": "completed",
            "output": {"message": f"Skill {tool_chain.skill_id} executed successfully"},
        }

        elapsed_ms = (time.monotonic() - start) * 1000

        self._execution_log.append({
            "skill_id": tool_chain.skill_id,
            "timestamp": time.time(),
            "latency_ms": round(elapsed_ms, 2),
            "status": result["status"],
        })

        return result

    def get_skill(self, skill_id: str) -> SkillManifest | None:
        """获取已缓存的 Skill 清单"""
        return self._skill_cache.get(skill_id)

    def list_skills(self, status: SkillStatus | None = None) -> list[SkillManifest]:
        """列出所有 Skill，可按状态过滤"""
        skills = list(self._skill_cache.values())
        if status:
            skills = [s for s in skills if s.status == status]
        return skills

    def update_status(self, skill_id: str, new_status: SkillStatus) -> bool:
        """更新 Skill 状态"""
        skill = self._skill_cache.get(skill_id)
        if skill is None:
            return False
        skill.status = new_status
        logger.info("Skill %s status updated to %s", skill_id, new_status.value)
        return True

    @staticmethod
    def _infer_name(repo_url: str) -> str:
        parts = repo_url.rstrip("/").split("/")
        return parts[-1] if parts else "unknown-skill"

    @staticmethod
    def _infer_author(repo_url: str) -> str:
        if "github.com" in repo_url:
            parts = repo_url.split("github.com/")[-1].split("/")
            return parts[0] if len(parts) > 1 else "anonymous"
        return "anonymous"

    def register_call(self, call: SkillCall) -> None:
        """记录 Skill 调用"""
        call.status = "completed"
        self._execution_log.append({
            "call_id": call.call_id,
            "skill_id": call.skill_id,
            "caller_id": call.caller_id,
            "revenue_usd": call.revenue_usd,
            "timestamp": call.timestamp,
        })
