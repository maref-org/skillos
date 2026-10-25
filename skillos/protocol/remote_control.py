#!/usr/bin/env python3
"""Remote Bridge Control — 远程桥接控制器

职责:
  - 远程 API 控制接口
  - 桥接连接管理
  - 远程命令分发
  - 会话状态查询
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# 心跳过期阈值：超过该时长未心跳的桥接会话视为失联，惰性回收
BRIDGE_HEARTBEAT_TTL = 120.0


@dataclass
class BridgeSession:
    session_id: str
    remote_url: str
    api_key: str
    status: str = "disconnected"
    last_heartbeat: float = 0.0
    connected_at: float = 0.0


@dataclass
class RemoteCommand:
    command: str
    session_id: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    timeout: int = 300


@dataclass
class RemoteControlResponse:
    status: str
    result: Any | None = None
    error: str | None = None


class RemoteBridge:
    """远程桥接控制器"""

    def __init__(self):
        self.active_bridges: dict[str, BridgeSession] = {}

    async def connect_bridge(
        self,
        session_id: str,
        remote_url: str,
        api_key: str,
    ) -> dict:
        """连接远程桥接"""
        import time

        bridge = BridgeSession(
            session_id=session_id,
            remote_url=remote_url,
            api_key=api_key,
            status="connected",
            last_heartbeat=time.time(),
            connected_at=time.time(),
        )
        self.active_bridges[session_id] = bridge
        logger.info("Bridge connected: %s -> %s", session_id, remote_url)
        return {"status": "connected", "session_id": session_id}

    async def disconnect_bridge(self, session_id: str) -> dict:
        """断开远程桥接"""
        bridge = self.active_bridges.pop(session_id, None)
        if bridge:
            bridge.status = "disconnected"
            logger.info("Bridge disconnected: %s", session_id)
            return {"status": "disconnected", "session_id": session_id}
        raise ValueError(f"Bridge not found: {session_id}")

    async def get_bridge_status(self, session_id: str) -> dict:
        """获取桥接状态"""
        bridge = self.active_bridges.get(session_id)
        if not bridge:
            raise ValueError(f"Bridge not found: {session_id}")
        return {
            "session_id": bridge.session_id,
            "status": bridge.status,
            "remote_url": bridge.remote_url,
            "last_heartbeat": bridge.last_heartbeat,
            "connected_at": bridge.connected_at,
        }

    async def list_bridges(self) -> list[dict]:
        """列出所有活跃桥接（惰性清理心跳过期会话）"""
        self._purge_stale()
        return [
            {
                "session_id": b.session_id,
                "status": b.status,
                "remote_url": b.remote_url,
                "last_heartbeat": b.last_heartbeat,
            }
            for b in self.active_bridges.values()
        ]

    async def execute_remote_command(self, cmd: RemoteCommand) -> RemoteControlResponse:
        """执行远程命令"""
        try:
            session_id = cmd.session_id or await self._create_session()

            command_handlers = {
                "skill_execute": self._handle_skill_execute,
                "session_create": self._handle_session_create,
                "session_close": self._handle_session_close,
                "state_query": self._handle_state_query,
                "bridge_connect": self._handle_bridge_connect,
                "bridge_disconnect": self._handle_bridge_disconnect,
            }

            handler = command_handlers.get(cmd.command)
            if not handler:
                return RemoteControlResponse(
                    status="error",
                    error=f"Unknown command: {cmd.command}",
                )

            result = await handler(session_id, cmd.params, cmd.timeout)
            return RemoteControlResponse(status="success", result=result)
        except Exception as e:
            logger.error("Remote command failed: %s", e)
            return RemoteControlResponse(status="error", error=str(e))

    async def _create_session(self) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        return session_id

    async def _handle_skill_execute(
        self,
        session_id: str,
        params: dict,
        timeout: int,
    ) -> dict:
        """处理技能执行命令"""
        skill_name = params.get("skill_name", "")
        input_data = params.get("input_data", {})
        logger.info("Remote skill execute: %s (session: %s)", skill_name, session_id)
        return {
            "session_id": session_id,
            "skill_name": skill_name,
            "status": "dispatched",
            "input_data": input_data,
        }

    async def _handle_session_create(
        self,
        session_id: str,
        params: dict,
        timeout: int,
    ) -> dict:
        """处理会话创建命令"""
        user_id = params.get("user_id", "remote")
        new_session_id = str(uuid.uuid4())
        logger.info("Remote session create: %s (user: %s)", new_session_id, user_id)
        return {"session_id": new_session_id, "user_id": user_id, "status": "created"}

    async def _handle_session_close(
        self,
        session_id: str,
        params: dict,
        timeout: int,
    ) -> dict:
        """处理会话关闭命令"""
        logger.info("Remote session close: %s", session_id)
        return {"session_id": session_id, "status": "closed"}

    async def _handle_state_query(
        self,
        session_id: str,
        params: dict,
        timeout: int,
    ) -> dict:
        """处理状态查询命令"""
        key = params.get("key", "")
        logger.debug("Remote state query: %s/%s", session_id, key)
        return {"session_id": session_id, "key": key, "state": None}

    async def _handle_bridge_connect(
        self,
        session_id: str,
        params: dict,
        timeout: int,
    ) -> dict:
        """处理桥接连接命令"""
        remote_url = params.get("remote_url", "")
        api_key = params.get("api_key", "")
        return await self.connect_bridge(session_id, remote_url, api_key)

    async def _handle_bridge_disconnect(
        self,
        session_id: str,
        params: dict,
        timeout: int,
    ) -> dict:
        """处理桥接断开命令"""
        return await self.disconnect_bridge(session_id)

    async def update_heartbeat(self, session_id: str) -> bool:
        """更新桥接心跳"""
        import time

        bridge = self.active_bridges.get(session_id)
        if bridge:
            bridge.last_heartbeat = time.time()
            return True
        return False

    def get_stats(self) -> dict:
        """获取桥接统计（惰性清理心跳过期会话）"""
        self._purge_stale()
        connected = sum(1 for b in self.active_bridges.values() if b.status == "connected")
        return {
            "total_bridges": len(self.active_bridges),
            "connected_bridges": connected,
            "disconnected_bridges": len(self.active_bridges) - connected,
        }

    def _purge_stale(self) -> None:
        """清理心跳超过 TTL 未刷新的桥接会话。"""
        now = time.time()
        stale = [sid for sid, b in self.active_bridges.items() if now - b.last_heartbeat > BRIDGE_HEARTBEAT_TTL]
        for sid in stale:
            bridge = self.active_bridges.pop(sid, None)
            if bridge:
                bridge.status = "disconnected"
                logger.info("Bridge heartbeat expired, purged: %s", sid)
