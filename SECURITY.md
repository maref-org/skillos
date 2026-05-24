# Security Policy

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security issues to the SkillOS security team via email at security@skillos.dev.
Include as much detail as possible: affected component, steps to reproduce,
potential impact, and suggested fix if available.

You will receive a response within 48 hours. We will keep you updated on
the remediation progress and credit you in the security advisory (unless
you request anonymity).

## Supported Versions

| Version | Supported          |
|---------|-------------------|
| 0.3.x   | Active support    |
| < 0.3   | End of life       |

## Security Architecture

SkillOS implements a defense-in-depth architecture for skill execution security:

Key security features:
- **Human-in-the-Loop (HITL) Gate**: Critical operations require explicit human approval
- **CircuitBreaker**: 3 consecutive failures trigger automatic lockout
- **Sandboxed Skill Execution**: Skills run in isolated environments with limited permissions
- **AuditLogger**: Append-only, HMAC-signed audit trail
- **Dependency Scanning**: Automated vulnerability checks via pip-audit and Bandit

## Security Best Practices

When deploying SkillOS in production:

1. Always run with `SKILLOS_SAFETY_LEVEL=production`
2. Enable HITL gating for all high-risk operations (deploy, delete, payment)
3. Grant only the minimum required OS permissions to skill processes
4. Review audit logs regularly
5. Keep dependencies updated (`pip list --outdated`)
6. Scan skills before registration for malicious code
