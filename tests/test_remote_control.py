"""Tests for M7-P3.2 — RemoteBridge 心跳过期回收（惰性清理）"""

import pytest

from skillos.protocol.remote_control import RemoteBridge


@pytest.mark.asyncio
async def test_stale_bridge_purged_from_list():
    bridge = RemoteBridge()
    await bridge.connect_bridge("live-1", "https://peer.example.com", "k")
    await bridge.connect_bridge("stale-1", "https://peer.example.com", "k")
    # 把 stale-1 的心跳时间拨回 TTL 之前（默认 120s）
    import time

    bridge.active_bridges["stale-1"].last_heartbeat = time.time() - 200
    bridges = await bridge.list_bridges()
    ids = {b["session_id"] for b in bridges}
    assert "stale-1" not in ids
    assert "live-1" in ids


@pytest.mark.asyncio
async def test_stats_excludes_stale_bridges():
    bridge = RemoteBridge()
    await bridge.connect_bridge("live-1", "https://peer.example.com", "k")
    await bridge.connect_bridge("stale-1", "https://peer.example.com", "k")
    import time

    bridge.active_bridges["stale-1"].last_heartbeat = time.time() - 200
    stats = bridge.get_stats()
    assert stats["total_bridges"] == 1
    assert stats["connected_bridges"] == 1


@pytest.mark.asyncio
async def test_heartbeat_refreshes_bridge():
    bridge = RemoteBridge()
    await bridge.connect_bridge("live-1", "https://peer.example.com", "k")
    import time

    bridge.active_bridges["live-1"].last_heartbeat = time.time() - 200
    ok = await bridge.update_heartbeat("live-1")
    assert ok is True
    bridges = await bridge.list_bridges()
    assert any(b["session_id"] == "live-1" for b in bridges)
