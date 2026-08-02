# Security Policy

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security issues to the SkillOS security team via email.
Include as much detail as possible: affected component, steps to reproduce,
potential impact, and suggested fix if available.

You will receive a response within 48 hours. We will keep you updated on
the remediation progress and credit you in the security advisory (unless
you request anonymity).

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.5.x   | ✅ Active support  |
| 0.4.x   | ⏳ Limited support |
| < 0.4   | ❌ End of life     |

## Security Architecture

SkillOS implements a **defense-in-depth** architecture for AI agent security:

| Layer | Feature | Description |
|-------|---------|-------------|
| L1 | Sandbox Isolation | Process-level execution isolation with resource limits, timeouts, and cleanup |
| L2 | Identity & Signing | Ed25519 challenge-response authentication with HMAC-SHA256 audit chain |
| L3 | Input Validation | Intent classification + risk assessment + keyword filtering |
| L4 | Human-in-the-Loop | High-risk operations require human gate approval before execution |
| L5 | Audit Logging | Append-only, HMAC-signed audit trail for all sensitive operations |
| L6 | Anti-Pattern Detection | NegMarket-based adversarial pattern recognition and warning |
| L7 | Secret Scanning | TruffleHog + pre-commit hooks prevent credential leakage |
| L8 | Dependency Auditing | pip-audit + Dependabot for CVE monitoring |

## Security Best Practices

When deploying SkillOS in production:

1. Always set `SKILLOS_API_KEY` via environment variable (never in code)
2. Use `--insecure` flag only for local development
3. Enable all audit logging and monitor logs regularly
4. Review pre-commit security hooks before bypassing
5. Keep dependencies updated (`pip list --outdated`)
6. Run `make security` before any release
