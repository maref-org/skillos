---
schema_version: "1.0"
type: design_doc
purpose: "Document retrieval policy with RL training - learn which docs help which tasks"
version: "0.1.0"
updated: "2026-07-30"
tags: [skillos, retrieval, rl, policy, reward]
freshness:
  updated: "2026-07-30"
  status: active
agent_instruction: "RL 检索策略模块。Agent 文档检索时通过 policy.py 对候选文档评分排序。训练后权重自动更新。"
cross_reference:
  - "../audit.py - 审计模块（reward_logger 依赖）"
  - "../../scripts/train_retrieval_policy.py - GRPO 训练脚本"
  - "../../data/reward_logs.jsonl - 奖励日志"
---

# Retrieval Policy — RL-optimized Document Selection

## Problem

Agents waste time reading irrelevant documents. The KB has 1,644+ .md files
across multiple projects. Static folder structure alone cannot optimize the
retrieval path for every task type.

## Solution: Two-Layer Architecture

```
Task arrives
  │
  ▼
Layer 1: Policy (policy.py)
  │  Scores all candidates by: 
  │    w1 × tag_similarity(task, doc)
  │  + w2 × freshness_score(doc)
  │  + w3 × cross_ref_score(doc)
  │  + w4 × past_reward(doc, similar_tasks)
  │  Returns top-k ranked docs
  ▼
Agent reads selected docs → executes task
  │
  ▼
Layer 2: Reward Logger (reward_logger.py)
  │  Records:
  │    - Which docs were read
  │    - Task outcome (success/fail)
  │    - Time spent reading
  │  → (doc_id, task_type, reward) triple
  ▼
Training Loop (scripts/train_retrieval_policy.py)
  │  Batch collects reward_logs
  │  Runs GRPO to update w1/w2/w3/w4
  │  Pushes updated weights to policy.py
  ▼
Improved policy for next task
```

## Initial Policy

The initial scoring function uses hand-tuned weights:

```python
score = 0.40 × tag_match(task_tags, doc_tags)
      + 0.25 × freshness(doc.updated)
      + 0.20 × cross_ref_match(task, doc)
      + 0.15 × base_boost(doc.type)  # directory_root > source_module > archive
```

These weights are optimized by GRPO as reward_logs accumulate.

## Reward Signal

| Signal | Weight | Source |
|--------|--------|--------|
| Task success | +1.0 if completed, -0.5 if failed | SLO/SkillKernel outcome |
| Doc efficiency | +0.3 if ≤3 docs read, -0.1 per extra doc | audit_log reader count |
| Freshness penalty | -0.2 if cited doc >90d stale | doc.updated field |
| Contamination penalty | -0.5 if doc contains /Volumes/ paths | grep on cited doc |

## Training Cadence

- `scripts/train_retrieval_policy.py` runs weekly (or on-demand)
- Uses GRPO (Group Relative Policy Optimization) — no critic network needed
- Samples 64 tasks from recent reward_logs, groups by task_type
- Updates policy weights, writes to `data/retrieval_weights.json`

## Integration Points

| Existing Module | How it Connects |
|----------------|-----------------|
| `skillos/audit.py` | Every doc read is logged as an audit event with doc_path |
| `skillos/kernel/slo.py` | Task success/failure feeds reward signal |
| `skillos/protocol/agent_card.py` | Which agent read which docs |
| `scripts/meta_monitor.py` | M2 reward loop closure check |

## Files

| File | Purpose |
|------|---------|
| `policy.py` | Retrieval scoring function + weight loader |
| `reward_logger.py` | Logs (task, doc, reward) triples to JSONL |
| `data/retrieval_weights.json` | Learned weights (updated by training) |
| `data/reward_logs.jsonl` | Raw training data |
| `scripts/train_retrieval_policy.py` | GRPO training loop |
