---
schema_version: "1.0"
type: source_module
purpose: "Execution sandbox — process isolation for untrusted skill code"
files:
  - "process_sandbox.py: Resource-limited subprocess execution (rlimit, temp isolation)"
  - "__init__.py: SandboxResult, SandboxConfig exports"
freshness:
  updated: "2026-07-04"
  version: "0.5.0-beta"
entry_point: "process_sandbox.py"
agent_instruction: |
  Sandbox for executing untrusted skill code in an isolated process.
  - Resource limits: CPU time, memory, file descriptors (setrlimit)
  - Filesystem isolation: temp directory per execution
  - Timeout: automatic process termination
  - Cross-platform: macOS + Linux
  If a task involves "running user-submitted code" or "skill isolation", start here.
tags: [skillos, sandbox, isolation, security, execution]
cross_reference:
  - "skillos/security/ (content-level safety)"
  - "skillos/kernel/skill_kernel.py (calls sandbox for skill execution)"
---

# sandbox/

Process sandbox for isolated skill code execution. Resource limits + temp filesystem.
