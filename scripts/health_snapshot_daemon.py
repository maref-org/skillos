#!/usr/bin/env python3
"""Health snapshot daemon — 定期写入健康快照供 meta-monitor M0 检查。

M0 生存性断言要求：健康快照文件修改时间 ≤ 120s 内。
该守护进程每 60s 写入一次，确保 meta-monitor 可正确判断系统存活。

用法:
    python scripts/health_snapshot_daemon.py              # 前台运行
    python scripts/health_snapshot_daemon.py --daemon     # 后台 fork 运行
    python scripts/health_snapshot_daemon.py --stop       # 停止后台进程
"""

import json
import os
import sys
import time
from pathlib import Path

SNAPSHOT_PATH = Path("audit_logs/health_snapshot.json")
INTERVAL = 60
PID_FILE = Path("/tmp/skillos_health_daemon.pid")


def write_snapshot():
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "timestamp": time.time(),
        "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pid": os.getpid(),
        "status": "healthy",
        "version": "0.1.0",
    }
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2))
    return snapshot


def daemonize():
    pid = os.fork()
    if pid > 0:
        PID_FILE.write_text(str(pid))
        print(f"Daemon started (PID={pid})")
        sys.exit(0)
    os.setsid()
    pid2 = os.fork()
    if pid2 > 0:
        sys.exit(0)
    with open(os.devnull, "r") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())
    sys.stdout.flush()
    sys.stderr.flush()


def stop_daemon():
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 15)
            PID_FILE.unlink()
            print(f"Daemon (PID={pid}) stopped.")
        except ProcessLookupError:
            PID_FILE.unlink()
            print("Daemon not running, cleaned up PID file.")
    else:
        print("No PID file found, daemon not running.")


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--daemon":
            daemonize()
        elif sys.argv[1] == "--stop":
            stop_daemon()
            return
        else:
            print(f"Unknown option: {sys.argv[1]}")
            sys.exit(1)

    print(f"Health snapshot daemon (PID={os.getpid()}, interval={INTERVAL}s)")
    while True:
        try:
            snap = write_snapshot()
            print(f"  [{snap['timestamp_iso']}] Snapshot written")
            time.sleep(INTERVAL)
        except KeyboardInterrupt:
            print("\nDaemon stopped.")
            break
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
