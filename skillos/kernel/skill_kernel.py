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
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from skillos.types import SkillCall, SkillManifest, SkillStatus
from skillos.db.engine import get_sessionmaker
from skillos.db.models import SkillModel, SkillNFTModel
from skillos.db.repository import SkillNFTRepository, SkillRepository

logger = logging.getLogger(__name__)


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
    """技能内核 — Skill 生命周期管理

    数据持久化：
      - _skill_cache 保留为内存缓存，但 DB 为唯一真相源
      - 所有写操作同步到数据库
      - 读操作优先查缓存，miss 时查 DB 并回填
    """

    def __init__(self, registry: Any | None = None, db_session: Any | None = None):
        self.registry = registry
        self._skill_cache: dict[str, SkillManifest] = {}
        self._nft_records: list[SkillNFT] = []
        self._execution_log: list[dict[str, Any]] = []
        self._db_session = db_session
        # 并发控制锁
        self._cache_lock = threading.RLock()
        self._log_lock = threading.Lock()
        self._execute_lock = threading.Lock()

    def _get_db(self):
        if self._db_session is not None:
            return self._db_session
        return get_sessionmaker()()

    @staticmethod
    def _manifest_to_model(manifest: SkillManifest) -> SkillModel:
        return SkillModel(
            id=manifest.id,
            name=manifest.name,
            version=manifest.version,
            author=manifest.author,
            description=manifest.description,
            license_type=manifest.license_type,
            status=manifest.status.value,
            entry_point=manifest.entry_point,
            dependencies=manifest.dependencies,
            price_per_call=manifest.price_per_call,
            metadata_json=manifest.metadata,
        )

    @staticmethod
    def _model_to_manifest(model: SkillModel) -> SkillManifest:
        return SkillManifest(
            id=model.id,
            name=model.name,
            version=model.version,
            author=model.author,
            description=model.description,
            license_type=model.license_type,
            status=SkillStatus(model.status),
            entry_point=model.entry_point,
            dependencies=model.dependencies,
            price_per_call=model.price_per_call,
            metadata=model.metadata_json,
            created_at=model.created_at.timestamp(),
        )

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

        # 持久化到 DB
        db = self._get_db()
        try:
            repo = SkillRepository(db)
            repo.save(self._manifest_to_model(manifest))
        finally:
            if self._db_session is None:
                db.close()

        with self._cache_lock:
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

        # 持久化到 DB
        db = self._get_db()
        try:
            nft_repo = SkillNFTRepository(db)
            nft_repo.save(
                SkillNFTModel(
                    skill_id=nft.skill_id,
                    token_id=nft.token_id,
                    owner=nft.owner,
                    metadata_hash=nft.metadata_hash,
                )
            )
        finally:
            if self._db_session is None:
                db.close()

        with self._log_lock:
            self._nft_records.append(nft)
        logger.info("Skill NFT minted: %s for %s", nft.token_id, nft.owner)
        return nft

    def assemble_tools(self, nft: SkillNFT) -> ToolChain:
        """组装工具链（MCP Connector + A2A Adapter）"""
        skill = self.get_skill(nft.skill_id)
        if skill is None:
            raise ValueError(f"Skill {nft.skill_id} not found")

        tools = [
            {"name": "default_executor", "type": "python", "entry": skill.entry_point},
        ]

        return ToolChain(
            skill_id=nft.skill_id,
            tools=tools,
            mcp_connectors=[f"mcp://{nft.skill_id}"],
            a2a_adapters=[f"a2a://{nft.skill_id}"],
        )

    async def execute(self, tool_chain: ToolChain, input_data: dict[str, Any]) -> dict[str, Any]:
        """执行 Skill（带沙箱隔离和并发控制）"""
        start = time.monotonic()
        logger.info("Executing skill: %s with input: %s", tool_chain.skill_id, input_data)

        with self._execute_lock:
            # 沙箱隔离：根据 execution_env 选择执行策略
            if tool_chain.execution_env == "wasm_sandbox":
                result = self._execute_wasm_sandbox(tool_chain, input_data)
            elif tool_chain.execution_env == "docker":
                result = self._execute_docker_sandbox(tool_chain, input_data)
            elif tool_chain.execution_env == "subprocess":
                result = self._execute_subprocess_sandbox(tool_chain, input_data)
            else:
                # 默认安全策略：禁止直接执行未知环境
                result = {
                    "skill_id": tool_chain.skill_id,
                    "status": "rejected",
                    "error": f"Unsupported execution_env: {tool_chain.execution_env}",
                    "output": None,
                }

            elapsed_ms = (time.monotonic() - start) * 1000

            with self._log_lock:
                self._execution_log.append({
                    "skill_id": tool_chain.skill_id,
                    "timestamp": time.time(),
                    "latency_ms": round(elapsed_ms, 2),
                    "status": result["status"],
                })

        return result

    def _execute_wasm_sandbox(self, tool_chain: ToolChain, input_data: dict[str, Any]) -> dict[str, Any]:
        """WASM 沙箱执行（当前为进程级隔离模拟，生产环境应接入 wasmtime/wasmer）"""
        # 安全策略 1：输入大小限制
        import json
        payload = json.dumps(input_data)
        if len(payload) > 1024 * 1024:  # 1MB 限制
            return {
                "skill_id": tool_chain.skill_id,
                "status": "rejected",
                "error": "Input payload exceeds 1MB limit",
                "output": None,
            }

        # 安全策略 2：禁止敏感系统调用（模拟）
        forbidden_keywords = ["os.system", "subprocess", "eval(", "exec(", "__import__"]
        payload_lower = payload.lower()
        for keyword in forbidden_keywords:
            if keyword in payload_lower:
                return {
                    "skill_id": tool_chain.skill_id,
                    "status": "rejected",
                    "error": f"Forbidden keyword detected in input: {keyword}",
                    "output": None,
                }

        # 安全策略 3：CPU/内存资源限制（通过 subprocess 模拟）
        try:
            # 模拟 WASM 执行：在受限子进程中运行
            result = self._run_in_subprocess_with_limits(tool_chain, input_data)
            return result
        except Exception as exc:
            logger.error("WASM sandbox execution failed: %s", exc)
            return {
                "skill_id": tool_chain.skill_id,
                "status": "error",
                "error": str(exc),
                "output": None,
            }

    def _execute_docker_sandbox(self, tool_chain: ToolChain, input_data: dict[str, Any]) -> dict[str, Any]:
        """Docker 容器沙箱执行（预留接口）"""
        logger.info("Docker sandbox requested for skill: %s", tool_chain.skill_id)
        return {
            "skill_id": tool_chain.skill_id,
            "status": "rejected",
            "error": "Docker sandbox not yet implemented. Use wasm_sandbox or subprocess.",
            "output": None,
        }

    def _execute_subprocess_sandbox(self, tool_chain: ToolChain, input_data: dict[str, Any]) -> dict[str, Any]:
        """子进程沙箱执行（带资源限制）"""
        return self._run_in_subprocess_with_limits(tool_chain, input_data)

    def _run_in_subprocess_with_limits(self, tool_chain: ToolChain, input_data: dict[str, Any]) -> dict[str, Any]:
        """在受限子进程中运行 Skill 逻辑"""
        import json
        import subprocess
        import tempfile

        # 创建临时脚本文件
        script_content = f"""
import json
import sys

input_data = json.loads(sys.stdin.read())
result = {{
    "skill_id": "{tool_chain.skill_id}",
    "status": "completed",
    "output": {{"message": f"Skill {tool_chain.skill_id} executed successfully", "input_echo": input_data}}
}}
print(json.dumps(result))
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            script_path = f.name

        try:
            proc = subprocess.run(
                ["python3", script_path],
                input=json.dumps(input_data),
                capture_output=True,
                text=True,
                timeout=5,  # 5 秒超时
            )
            if proc.returncode != 0:
                return {
                    "skill_id": tool_chain.skill_id,
                    "status": "error",
                    "error": proc.stderr,
                    "output": None,
                }
            return json.loads(proc.stdout)
        except subprocess.TimeoutExpired:
            return {
                "skill_id": tool_chain.skill_id,
                "status": "error",
                "error": "Execution timeout (5s)",
                "output": None,
            }
        except Exception as exc:
            return {
                "skill_id": tool_chain.skill_id,
                "status": "error",
                "error": str(exc),
                "output": None,
            }
        finally:
            import os
            try:
                os.unlink(script_path)
            except OSError:
                pass

    def get_skill(self, skill_id: str) -> SkillManifest | None:
        """获取已缓存的 Skill 清单（缓存优先，DB 回填）"""
        with self._cache_lock:
            if skill_id in self._skill_cache:
                return self._skill_cache[skill_id]

        db = self._get_db()
        try:
            repo = SkillRepository(db)
            model = repo.get(skill_id)
            if model is None:
                return None
            manifest = self._model_to_manifest(model)
            with self._cache_lock:
                self._skill_cache[skill_id] = manifest
            return manifest
        finally:
            if self._db_session is None:
                db.close()

    def list_skills(self, status: SkillStatus | None = None) -> list[SkillManifest]:
        """列出所有 Skill，可按状态过滤（优先从 DB 加载）"""
        db = self._get_db()
        try:
            repo = SkillRepository(db)
            models = repo.list_all(status=status.value if status else None)
            manifests = [self._model_to_manifest(m) for m in models]
            # 同步刷新缓存
            with self._cache_lock:
                for m in manifests:
                    self._skill_cache[m.id] = m
            return manifests
        finally:
            if self._db_session is None:
                db.close()

    def update_status(self, skill_id: str, new_status: SkillStatus) -> bool:
        """更新 Skill 状态"""
        db = self._get_db()
        try:
            repo = SkillRepository(db)
            model = repo.get(skill_id)
            if model is None:
                return False
            model.status = new_status.value
            repo.save(model)
            # 同步更新缓存
            with self._cache_lock:
                cached = self._skill_cache.get(skill_id)
                if cached:
                    cached.status = new_status
            logger.info("Skill %s status updated to %s", skill_id, new_status.value)
            return True
        finally:
            if self._db_session is None:
                db.close()

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
        with self._log_lock:
            self._execution_log.append({
                "call_id": call.call_id,
                "skill_id": call.skill_id,
                "caller_id": call.caller_id,
                "revenue_usd": call.revenue_usd,
                "timestamp": call.timestamp,
            })
