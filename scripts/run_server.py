#!/usr/bin/env python3
"""启动真实 SkillOS HTTP 服务（uvicorn）。

用法::
    .venv/bin/python scripts/run_server.py [--port 8080] [--host 127.0.0.1]
    # 或
    SKILLOS_PAYMENT_PROVIDER=sandbox .venv/bin/python scripts/run_server.py

端点（M6 完整集）:
    /api/v1/agent/*       MCP 风格 Agent 端点
    /api/v1/outcome/*     成果契约闭环
    /api/v1/payments/*    持牌支付桥接（webhook / submit / providers）
    /health               健康检查
    /metrics              Prometheus 指标
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real SkillOS HTTP service")
    parser.add_argument("--host", default=os.environ.get("SKILLOS_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SKILLOS_PORT", "8080")))
    args = parser.parse_args()

    import uvicorn

    from skillos.app import app

    if app is None:
        print("ERROR: FastAPI not installed. Run: .venv/bin/pip install 'skillos-os[web]'")
        return 1

    print(f"SkillOS HTTP service: http://{args.host}:{args.port}")
    print("  health:      GET /health")
    print("  payments:    /api/v1/payments/providers")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
