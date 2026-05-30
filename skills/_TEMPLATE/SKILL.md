---
name: skill-name
description: "What this skill does and when to trigger it"
version: "1.0.0"
autoApply: false
dependencies: []
platforms:
  - claude
  - opencode
  - trae
triggers:
  - "trigger phrase 1"
  - "trigger phrase 2"
input_schema:
  type: object
  properties: {}
output_schema:
  type: object
  properties: {}
sla:
  target_success_rate: 0.95
  max_latency_ms: 5000
changelog:
  - version: "1.0.0"
    date: "YYYY-MM-DD"
    changes: "Initial version"
---

# Skill: skill-name

## Overview
[One sentence about what this skill does]

## When to Use
[Trigger conditions and keywords]

## Core Instructions
[The main instructions for the agent]

## Examples
### Success
```
[Expected successful output]
```

### Failure
```
[Expected failure output and recovery]
```

## Testing
- [Test case 1]
- [Test case 2]

## Changelog
See frontmatter.
