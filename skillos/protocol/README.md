---
schema_version: "1.0"
type: source_module
purpose: "Men0 protocol — agent identity, cards, remote control, mDNS discovery"
files:
  - "agent_card.py: AgentRegistry (SQLite), AgentCard, heartbeat, prune_inactive"
  - "remote_control.py: BridgeControl — WebSocket remote session management"
  - "mdns.py: mDNS discovery for peer agents"
freshness:
  updated: "2026-07-04"
  version: "0.5.0-beta"
entry_point: "agent_card.py"
agent_instruction: |
  Agent identity and communication layer.
  - Registration: AgentRegistry.register(card)
  - Heartbeat: AgentRegistry.heartbeat(agent_id) + prune_inactive(timeout)
  - Discovery: AgentRegistry.discover(capability="...")
  - Remote control: BridgeControl for multi-agent remote sessions
  If a task involves "finding agents" or "agent status", start in agent_card.py.
  The heartbeat mechanism here feeds the meta-audit M0 survivability check.
tags: [skillos, protocol, agent, identity, heartbeat, discovery]
cross_reference:
  - "skillos/audit.py (audit logs track agent lifecycle events)"
---

# protocol/

Men0 protocol — agent identity, registration, heartbeat, and remote control.
