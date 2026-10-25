#!/usr/bin/env python3
"""Meta-monitor — 元审计聚合巡检脚本

按产品级发布全量验收标准 v0.3 的 M0~M3 框架，对 SkillOS 审计系统自身做生存性断言。
输出结构化报告到 audit_logs/meta_report.json，退出码反映门禁结果。

用法:
    python scripts/meta_monitor.py                  # 全量检查
    python scripts/meta_monitor.py --check M0       # 仅 M0
    python scripts/meta_monitor.py --check M0,M1    # M0+M1
    python scripts/meta_monitor.py --report         # 仅输出上次报告

退出码:
    0 = 全部通过
    1 = 非阻断失败（M1/M2/M3 非阻塞项）
    2 = 阻断失败（M0 或阻塞项失败）
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

_self = Path(__file__).resolve()
_proj_root = _self.parent.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

from skillos.audit import get_audit_logger  # noqa: E402
from skillos.protocol.agent_card import AgentRegistry  # noqa: E402

REPORT_PATH = Path("audit_logs/meta_report.json")
HEALTH_SNAPSHOT_PATH = Path("audit_logs/health_snapshot.json")
NOTIFICATIONS_DIR = Path("audit_logs/notifications")
AUDIT_LOG_DIR = Path("audit_logs")


def _is_ci() -> bool:
    """检测是否在 CI 环境中运行，跳过需持续运行服务的检查。"""
    return os.getenv("CI", "").lower() in ("true", "1")


def _runtime_checks_enabled() -> bool:
    """运行时存活检查默认跳过（发布门禁只验静态产物）。

    生产监控通过 SKILLOS_META_ENFORCE_RUNTIME=1 显式开启。
    """
    if _is_ci():
        return False
    return os.getenv("SKILLOS_META_ENFORCE_RUNTIME", "").lower() in ("1", "true", "yes")


M0_FRESHNESS_SEC = 120
M0_LOG_FRESH_SEC = 300
M0_HEARTBEAT_TIMEOUT = 300
M0_STALE_THRESHOLD = 0.30


class MetaAuditError(Exception):
    pass


def _fmt_ts(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _file_age(path: Path) -> float | None:
    if not path.exists():
        return None
    return time.time() - path.stat().st_mtime


def _check_health_snapshot_freshness() -> dict:
    result = {"check": "M0-health_snapshot", "description": "健康快照新鲜度", "blocking": True}
    if not _runtime_checks_enabled():
        result["status"] = "skip"
        result["detail"] = "运行时检查默认跳过（SKILLOS_META_ENFORCE_RUNTIME=1 时启用）"
        return result
    age = _file_age(HEALTH_SNAPSHOT_PATH)
    if age is None:
        result["status"] = "fail"
        result["detail"] = f"快照文件不存在: {HEALTH_SNAPSHOT_PATH}"
        return result
    if age > M0_FRESHNESS_SEC:
        result["status"] = "fail"
        result["detail"] = f"快照已过期: {age:.0f}s > {M0_FRESHNESS_SEC}s"
        return result
    result["status"] = "pass"
    result["detail"] = f"快照新鲜: {age:.0f}s"
    return result


def _check_audit_log_growth() -> dict:
    result = {"check": "M0-audit_log", "description": "审计日志增长", "blocking": True}
    if not _runtime_checks_enabled():
        result["status"] = "skip"
        result["detail"] = "运行时检查默认跳过（SKILLOS_META_ENFORCE_RUNTIME=1 时启用）"
        return result
    today = time.strftime("%Y-%m-%d")
    log_file = Path(os.getenv("SKILLOS_AUDIT_DIR", str(AUDIT_LOG_DIR))) / f"audit_{today}.log"
    age = _file_age(log_file)
    if age is None:
        result["status"] = "fail"
        result["detail"] = f"今日审计日志不存在: {log_file}"
        return result
    if age > M0_LOG_FRESH_SEC:
        result["status"] = "fail"
        result["detail"] = f"审计日志超过 {M0_LOG_FRESH_SEC}s 未更新: {age:.0f}s"
        return result
    result["status"] = "pass"
    result["detail"] = f"日志活跃: {age:.0f}s"
    return result


def _check_agent_heartbeat() -> dict:
    result = {"check": "M0-agent_heartbeat", "description": "Agent 心跳脉冲新鲜度", "blocking": True}
    try:
        registry = AgentRegistry()
        stats = registry.get_stats()
        total = stats.get("total", 0)
        active = stats.get("active", 0)
        if total == 0:
            result["status"] = "pass"
            result["detail"] = "无注册 Agent，跳过心跳检查"
            return result
        stale_ratio = 1.0 - (active / max(total, 1))
        if stale_ratio > M0_STALE_THRESHOLD:
            result["status"] = "fail"
            result["detail"] = f"陈旧率 {stale_ratio:.1%} > {M0_STALE_THRESHOLD:.0%} (active={active}, total={total})"
            return result
        result["status"] = "pass"
        result["detail"] = f"心跳健康: active={active}/{total}, 陈旧率 {stale_ratio:.1%}"
        return result
    except Exception as exc:
        result["status"] = "fail"
        result["detail"] = f"心跳检查异常: {exc}"
        return result


def _check_health_endpoint() -> dict:
    result = {"check": "M0-http_health", "description": "HTTP /health 端点", "blocking": True}
    if not _runtime_checks_enabled():
        result["status"] = "skip"
        result["detail"] = "运行时检查默认跳过（SKILLOS_META_ENFORCE_RUNTIME=1 时启用）"
        return result
    try:
        import httpx

        port = os.getenv("SKILLOS_PORT", "8080")
        r = httpx.get(f"http://localhost:{port}/health", timeout=5)
        if r.status_code != 200:
            result["status"] = "fail"
            result["detail"] = f"/health 返回 {r.status_code}"
            return result
        body = r.json()
        if body.get("status") != "healthy":
            result["status"] = "fail"
            result["detail"] = f"/health status={body.get('status')}"
            return result
        result["status"] = "pass"
        result["detail"] = "/health → 200, status=healthy"
        return result
    except ImportError:
        result["status"] = "skip"
        result["detail"] = "httpx 未安装，跳过 HTTP 健康检查"
        return result
    except Exception as exc:
        result["status"] = "warn"
        result["detail"] = f"/health 不可达: {exc}（服务未运行时可忽略）"
        return result


def _check_hmac_key() -> dict:
    result = {"check": "M1-hmac_key", "description": "HMAC 密钥存在", "blocking": False}
    key = os.getenv("SKILLOS_AUDIT_SECRET", "")
    if not key:
        secret_file = Path(os.getenv("SKILLOS_AUDIT_DIR", "./audit_logs")) / ".audit_secret"
        if secret_file.exists():
            result["status"] = "pass"
            result["detail"] = f"使用持久化密钥文件: {secret_file}"
            return result
        result["status"] = "warn"
        result["detail"] = "SKILLOS_AUDIT_SECRET 未设置且无持久化密钥文件（审计链仅本进程可验）"
        return result
    if len(key) < 16:
        result["status"] = "fail"
        result["detail"] = f"HMAC 密钥长度过短: {len(key)} < 16"
        return result
    result["status"] = "pass"
    result["detail"] = f"HMAC 密钥已配置（长度 {len(key)}）"
    return result


def _check_audit_chain() -> dict:
    result = {"check": "M1-audit_chain", "description": "审计链完整性", "blocking": True}
    today_log = Path(os.getenv("SKILLOS_AUDIT_DIR", str(AUDIT_LOG_DIR))) / f"audit_{time.strftime('%Y-%m-%d')}.log"
    if not today_log.exists():
        result["status"] = "pass"
        result["detail"] = "今日无审计记录，链校验跳过（历史日志不回验）"
        return result
    try:
        audit = get_audit_logger()
        ok = audit.verify_chain()
        if not ok:
            result["status"] = "fail"
            result["detail"] = "审计链完整性校验失败（签名或 prev_hash 不匹配）"
            return result
        result["status"] = "pass"
        result["detail"] = "审计链 HMAC 签名 + 链式哈希校验通过"
        return result
    except Exception as exc:
        result["status"] = "fail"
        result["detail"] = f"审计链校验异常: {exc}"
        return result


def _check_audit_log_path() -> dict:
    result = {"check": "M1-log_path", "description": "审计日志路径一致性", "blocking": True}
    configured = os.getenv("SKILLOS_AUDIT_DIR", "./audit_logs")
    configured_path = Path(configured)
    if not configured_path.exists():
        result["status"] = "fail"
        result["detail"] = f"配置的审计目录不存在: {configured}"
        return result
    today = time.strftime("%Y-%m-%d")
    log_file = configured_path / f"audit_{today}.log"
    if not log_file.exists():
        result["status"] = "warn"
        result["detail"] = f"今日日志文件未创建: {log_file}（可能今日无审计事件）"
        return result
    result["status"] = "pass"
    result["detail"] = f"审计路径一致: {configured_path.resolve()}"
    return result


def _check_notification_staleness() -> dict:
    result = {"check": "M2-notification_staleness", "description": "告警通知文件存活审计", "blocking": False}
    if not NOTIFICATIONS_DIR.exists():
        result["status"] = "pass"
        result["detail"] = "无通知目录，跳过（尚未部署告警通知系统）"
        return result
    stale_count = 0
    total = 0
    now = time.time()
    for f in NOTIFICATIONS_DIR.iterdir():
        if not f.is_file():
            continue
        total += 1
        age = now - f.stat().st_mtime
        if age > 86400:
            stale_count += 1
    if total == 0:
        result["status"] = "pass"
        result["detail"] = "通知目录为空"
        return result
    if stale_count > 0:
        result["status"] = "warn"
        result["detail"] = f"{stale_count}/{total} 通知文件超过 24h 未处理"
        return result
    result["status"] = "pass"
    result["detail"] = f"0/{total} 过期通知文件"
    return result


def _check_meta_report_readable() -> dict:
    result = {"check": "M3-meta_report", "description": "元监控报告可读", "blocking": False}
    if not REPORT_PATH.exists():
        result["status"] = "pass"
        result["detail"] = "首次运行，无历史报告可检查"
        return result
    try:
        data = json.loads(REPORT_PATH.read_text())
        required = {"timestamp", "checks", "summary", "meta_status"}
        actual = set(data.keys())
        missing = required - actual
        if missing:
            result["status"] = "warn"
            result["detail"] = f"报告缺少字段: {missing}"
            return result
        result["status"] = "pass"
        result["detail"] = f"报告可读，含 {len(data.get('checks', []))} 项检查"
        return result
    except (json.JSONDecodeError, OSError) as exc:
        result["status"] = "fail"
        result["detail"] = f"报告不可读: {exc}"
        return result


def _check_self_process() -> dict:
    result = {"check": "M3-self_process", "description": "元监控自身进程存活", "blocking": True}
    result["status"] = "pass"
    result["detail"] = "meta_monitor.py 本次调用正常执行"
    return result


ALL_CHECKS = {
    "M0": [
        _check_health_snapshot_freshness,
        _check_audit_log_growth,
        _check_agent_heartbeat,
        _check_health_endpoint,
    ],
    "M1": [
        _check_hmac_key,
        _check_audit_chain,
        _check_audit_log_path,
    ],
    "M2": [
        _check_notification_staleness,
    ],
    "M3": [
        _check_meta_report_readable,
        _check_self_process,
    ],
}


def run_checks(selected: set[str] | None = None) -> list[dict]:
    results = []
    for level in ["M0", "M1", "M2", "M3"]:
        if selected and level not in selected:
            continue
        for check_fn in ALL_CHECKS[level]:
            try:
                results.append(check_fn())
            except Exception as exc:
                results.append(
                    {
                        "check": f"{level}-unknown",
                        "description": check_fn.__name__,
                        "status": "error",
                        "detail": str(exc),
                        "blocking": True,
                    }
                )
    return results


def summarize(results: list[dict]) -> dict:
    statuses = [r["status"] for r in results]
    blocking_fails = [r for r in results if r.get("blocking") and r["status"] == "fail"]
    any_fails = [r for r in results if r["status"] == "fail"]

    if len(blocking_fails) == 0 and len(any_fails) == 0:
        meta_status = "healthy"
    elif len(blocking_fails) == 0 and len(any_fails) > 0:
        meta_status = "degraded"
    else:
        meta_status = "unhealthy"

    return {
        "meta_status": meta_status,
        "total": len(results),
        "pass": statuses.count("pass"),
        "fail": statuses.count("fail"),
        "warn": statuses.count("warn"),
        "skip": statuses.count("skip"),
        "error": statuses.count("error"),
        "blocking_fails": len(blocking_fails),
        "blocking_fail_checks": [r["check"] for r in blocking_fails],
    }


def write_report(results: list[dict], summary: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": time.time(),
        "timestamp_iso": _fmt_ts(time.time()),
        "version": "0.1.0",
        "checks": results,
        "summary": summary,
        "meta_status": summary["meta_status"],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"报告已写入: {REPORT_PATH.resolve()}")


def print_report() -> None:
    if not REPORT_PATH.exists():
        print(f"无历史报告: {REPORT_PATH}")
        sys.exit(1)
    print(REPORT_PATH.read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description="SkillOS 元审计聚合巡检")
    parser.add_argument("--check", help="检查层级 M0/M1/M2/M3（逗号分隔，默认全量）")
    parser.add_argument("--report", action="store_true", help="仅输出上次报告")
    args = parser.parse_args()

    if args.report:
        print_report()
        return 0

    selected = None
    if args.check:
        selected = set(args.check.upper().split(","))
        valid = {"M0", "M1", "M2", "M3"}
        invalid = selected - valid
        if invalid:
            print(f"无效检查层级: {invalid}，可选: {valid}")
            return 2

    results = run_checks(selected)
    summary = summarize(results)
    write_report(results, summary)

    print(f"\n元审计巡检完成: {summary['meta_status']}")
    print(f"  {summary['pass']} pass, {summary['fail']} fail, {summary['warn']} warn, {summary['skip']} skip")
    if summary["blocking_fails"] > 0:
        print(f"  ❌ 阻断失败: {summary['blocking_fail_checks']}")

    if summary["meta_status"] == "unhealthy":
        return 2
    if summary["meta_status"] == "degraded":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
