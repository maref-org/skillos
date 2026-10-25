"""``python -m skillos`` — HTTP 服务入口（容器与本地共用）。"""

from __future__ import annotations

import os

from skillos.app import app


def main() -> None:
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("SKILLOS_HOST", "127.0.0.1"),
        port=int(os.getenv("SKILLOS_PORT", "8080")),
        log_level=os.getenv("SKILLOS_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
