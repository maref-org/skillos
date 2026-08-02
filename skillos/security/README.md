---
schema_version: "1.0"
type: source_module
purpose: "Security — hallucination detection, threat intel, PII firewall, prompt protection"
files:
  - "hallucination_detector.py: 5-class rule-based detector (URL/date/entity/consistency)"
  - "threat_intel.py: Multi-source threat intelligence collector"
  - "pii_firewall.py: PII detection and redaction"
  - "prompt_protector.py: Input validation and prompt injection heuristics"
freshness:
  updated: "2026-07-04"
  version: "0.5.0-beta"
entry_point: "hallucination_detector.py"
agent_instruction: |
  Security modules for skill execution safety.
  - Hallucination detection: rules for URL validity, numerical consistency, date chronology
  - Threat intel: aggregates threat data from multi-source feeds
  - PII firewall: detects and redacts personal identifiable information
  - Prompt protector: input sanitization and injection detection
  If a task involves "is this skill output safe", start in hallucination_detector.py.
tags: [skillos, security, hallucination, pii, threat]
cross_reference:
  - "skillos/sandbox/ (execution isolation layer)"
---

# security/

Security modules — output validation, threat detection, PII protection.
