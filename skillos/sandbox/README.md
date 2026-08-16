---
schema_version: "1.0"
type: source_module
purpose: "Execution sandbox — isolated execution for untrusted skill code (process + container)"
files:
  - "process_sandbox.py: Resource-limited subprocess execution (rlimit, temp isolation). 资源限制，非安全边界。"
  - "container_sandbox.py: Docker 容器级安全隔离（无网络/只读/非 root/超时自终止）。P1#1 修复。"
  - "__init__.py: ProcessSandbox / DockerSandbox exports"
freshness:
  updated: "2026-08-16"
  version: "0.6.0"
entry_point: "process_sandbox.py"
agent_instruction: |
  Sandbox for executing untrusted skill code.
  - process_sandbox: Resource limits (CPU/memory/fd/rlimit) + temp isolation. 仅资源隔离，
    不可用于隔离不可信代码（process_sandbox.py 头部边界声明）。
  - container_sandbox: Docker 容器隔离（--network=none --read-only --cap-drop=ALL
    --security-opt=no-new-privileges --user=65534），脚本内 signal.alarm 超时自终止。
    Docker daemon 不可用时返回 status=rejected，不降级到不安全的进程沙箱。
  - skill_kernel docker execution_env → container_sandbox；wasm_sandbox 仍为进程模拟。
  若任务涉及"运行用户提交代码/技能隔离"，优先 container_sandbox。
tags: [skillos, sandbox, isolation, security, execution, docker]
cross_reference:
  - "skillos/security/ (content-level safety)"
  - "skillos/kernel/skill_kernel.py (calls sandbox for skill execution)"
  - "docs/go-no-go-2026-07-04.md (#1 WASM/Docker 沙箱 P1 例外)"
---

# sandbox/

Container-grade isolation (Docker) for untrusted code, with process-level resource
limiting as the portable fallback caveat. See per-module boundary notes.