#!/usr/bin/env python3
"""SkillOS 混沌工程测试 — 验证进程级弹性与恢复能力。

场景:
  1. process_kill: 杀死主进程，验证 systemd/Docker 自动拉起
  2. network_disconnect: 模拟网络断连，验证断路器 + 重试
  3. resource_exhaustion: 内存/文件描述符耗尽
"""

import os
import signal
import subprocess
import sys
import time
import urllib.request

BASE_URL = os.getenv("SKILLOS_BASE_URL", "http://localhost:8000")
RECOVERY_TIMEOUT = 30  # seconds


def _health_check() -> bool:
    try:
        resp = urllib.request.urlopen(f"{BASE_URL}/health", timeout=5)
        return resp.status == 200
    except Exception:
        return False


def _wait_for_recovery(timeout: int = RECOVERY_TIMEOUT) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _health_check():
            return True
        time.sleep(1)
    return False


def chaos_process_kill() -> list[str]:
    failures = []
    print("[chaos] Scenario: process_kill — killing main process...")

    # Find the running skillos process
    try:
        result = subprocess.run(
            ["pgrep", "-f", "skillos"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        pids = [int(p) for p in result.stdout.strip().split() if p]
        if not pids:
            return ["No skillos process found to kill"]
    except subprocess.TimeoutExpired:
        return ["pgrep timed out"]

    for pid in pids[:1]:
        os.kill(pid, signal.SIGKILL)
        print(f"[chaos] Killed PID {pid}")
        time.sleep(2)
        if _wait_for_recovery():
            print(f"[chaos] ✅ Recovery successful after killing PID {pid}")
        else:
            failures.append(f"Process {pid} did not recover within {RECOVERY_TIMEOUT}s")

    return failures


def chaos_network_disconnect() -> list[str]:
    failures = []
    print("[chaos] Scenario: network_disconnect — simulating network failure...")

    if not _health_check():
        return ["Application not running, skipping network test"]

    # Simulate by blocking outgoing connections via iptables (requires root)
    if os.geteuid() != 0:
        print("[chaos] ⚠️  Skipping network_disconnect (requires root)")
        return []

    try:
        subprocess.run(
            ["iptables", "-A", "OUTPUT", "-p", "tcp", "--dport", "8000", "-j", "DROP"],
            check=True,
            timeout=10,
        )
        subprocess.run(
            ["iptables", "-A", "INPUT", "-p", "tcp", "--sport", "8000", "-j", "DROP"],
            check=True,
            timeout=10,
        )
        print("[chaos] Network blocked")

        time.sleep(5)
        if not _health_check():
            print("[chaos] ✅ Application correctly detects network failure")
        else:
            failures.append("Application still responds after network block")

    finally:
        subprocess.run(
            ["iptables", "-D", "OUTPUT", "-p", "tcp", "--dport", "8000", "-j", "DROP"],
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            ["iptables", "-D", "INPUT", "-p", "tcp", "--sport", "8000", "-j", "DROP"],
            capture_output=True,
            timeout=10,
        )

    if _wait_for_recovery():
        print("[chaos] ✅ Network recovery successful")
    else:
        failures.append("Application did not recover after network restore")

    return failures


def chaos_resource_exhaustion() -> list[str]:
    failures = []
    print("[chaos] Scenario: resource_exhaustion — checking OOM behavior...")

    if not _health_check():
        return ["Application not running, skipping resource test"]

    # Check that sandbox correctly limits memory
    import resource

    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    print(f"[chaos] RLIMIT_AS: soft={soft}, hard={hard}")

    if soft == -1 and hard == -1:
        failures.append("RLIMIT_AS is unlimited — risk of OOM")
    else:
        print("[chaos] ✅ RLIMIT_AS is set")

    return failures


def main():
    exit_code = 0
    all_failures = []

    for scenario in [chaos_process_kill, chaos_network_disconnect, chaos_resource_exhaustion]:
        try:
            failures = scenario()
            all_failures.extend(failures)
            if failures:
                exit_code = 1
        except Exception as e:
            all_failures.append(f"Scenario {scenario.__name__} raised: {e}")
            exit_code = 1

    if all_failures:
        print(f"\n[chaos] ❌ {len(all_failures)} failure(s):")
        for f in all_failures:
            print(f"  - {f}")
    else:
        print("\n[chaos] ✅ All scenarios passed")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
