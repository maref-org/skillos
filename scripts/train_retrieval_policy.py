#!/usr/bin/env python3
"""Train retrieval policy weights using GRPO.

Collects recent reward_logs, groups by task_type, computes group-relative
advantages, and updates policy weights.

Usage:
    python scripts/train_retrieval_policy.py          # train on all recent logs
    python scripts/train_retrieval_policy.py --dry-run # preview without saving
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path

_self = Path(__file__).resolve()
_proj_root = _self.parent.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

from skillos.retrieval.policy import RetrievalPolicy  # noqa: E402
from skillos.retrieval.reward_logger import RewardLogger  # noqa: E402


def grpo_update(
    rewards: list[float],
    weights: dict[str, float],
    lr: float = 0.05,
    epsilon: float = 0.2,
) -> dict[str, float]:
    if not rewards:
        return weights

    mean = sum(rewards) / len(rewards)
    std = math.sqrt(sum((r - mean) ** 2 for r in rewards) / len(rewards)) or 1.0
    advantages = [(r - mean) / std for r in rewards]
    avg_advantage = sum(advantages) / len(advantages)

    updated = {}
    for key, w in weights.items():
        delta = lr * avg_advantage * w
        delta = max(-epsilon, min(epsilon, delta))
        updated[key] = round(max(0.01, w + delta), 4)

    total = sum(updated.values())
    if total > 0:
        updated = {k: round(v / total, 4) for k, v in updated.items()}

    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="GRPO retrieval policy trainer")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--lr", type=float, default=0.05, help="Learning rate")
    args = parser.parse_args()

    logger = RewardLogger()
    policy = RetrievalPolicy()

    outcomes = logger.query(limit=200)
    if not outcomes:
        print("No reward logs found. Run some tasks first.")
        return 0

    by_type: dict[str, list[float]] = defaultdict(list)
    for r in outcomes:
        reward = logger.compute_reward(r)
        by_type[r.get("task_type", "unknown")].append(reward)

    print(f"Found {len(outcomes)} task outcomes across {len(by_type)} types:\n")

    old_weights = dict(policy._weights)
    combined_rewards = [r for rr in by_type.values() for r in rr]
    new_weights = grpo_update(combined_rewards, old_weights, lr=args.lr)

    print(f"  {'Weight':<15} {'Before':<10} {'After':<10} {'Delta':<10}")
    print(f"  {'-'*45}")
    for key in sorted(old_weights):
        delta = new_weights.get(key, 0) - old_weights[key]
        print(f"  {key:<15} {old_weights[key]:<10.4f} {new_weights.get(key, 0):<10.4f} {delta:<+10.4f}")

    if args.dry_run:
        print("\n[Dry run] Not saving.")
        return 0

    policy.update_weights(new_weights)
    print("\nWeights saved to data/retrieval_weights.json")
    print(f"Average reward: {sum(combined_rewards)/len(combined_rewards):.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
