---
name: open-design-api
description: Open Design REST API wrapper — create design runs, manage projects, install design systems/skills/plugins, generate media, export artifacts. Use when user asks for "生成设计", "创建设计项目", "安装 design system", "导出设计", "调用 Open Design API".
---

# Open Design API Skill

> Programmatic access to Open Design (nexu-io/open-design) daemon running on localhost:60479.
> No Web UI needed — agent calls REST endpoints directly.

## When to Use

- Create a design run (chat-based generation) via API
- Install/import a DESIGN.md design system
- Install/import a skill
- Create/manage design projects
- Generate media (images, videos) for designs
- Export design artifacts (HTML, PDF, PPTX)
- List available design systems, skills, plugins
- Check daemon health and status

## Prerequisites

Open Design daemon must be running:

```bash
# Check health
curl -s http://127.0.0.1:60479/api/health

# If not running, start it:
bin/start-open-design.sh
```

## Base URL

```
API_BASE=${OPEN_DESIGN_API_BASE:-http://127.0.0.1:60479}
```

## Quick Reference

### Core Workflows

| Workflow | Steps |
|----------|-------|
| Create design | `POST /api/runs` → poll `GET /api/runs/:id` → get artifact |
| Chat generation | `POST /api/chat` (SSE stream) |
| Install design system | `POST /api/design-systems/import/local` |
| Create project | `POST /api/projects` → add files → deploy |
| Generate media | `POST /api/projects/:id/media/generate` |
| Export design | `POST /api/applied-plugins/export` |

### API Endpoints

#### Health & Status

```bash
GET /api/health
GET /api/version
GET /api/daemon/status
```

#### Design Runs (Async Generation)

```bash
# Create a design run
POST /api/runs
Body: { "message": "Create a dashboard with...", "designSystemId": "apple", "skillId": "dashboard" }
Response: { "runId": "abc123" }

# Check run status
GET /api/runs/:id
Response: { "id": "...", "status": "running|succeeded|failed|canceled", ... }

# Stream run events (SSE)
GET /api/runs/:id/events

# Cancel a run
POST /api/runs/:id/cancel

# List runs
GET /api/runs?projectId=xxx&status=succeeded
```

#### Chat (SSE Streaming)

```bash
POST /api/chat
Body: { "message": "Make a landing page...", "designSystemId": "apple" }
Response: SSE stream of agent tokens and artifacts
```

#### Design Systems

```bash
# List all design systems
GET /api/design-systems

# Get a specific design system
GET /api/design-systems/:id

# Preview a design system (HTML)
GET /api/design-systems/:id/preview

# Showcase (marketing page)
GET /api/design-systems/:id/showcase

# Install a design system from GitHub
POST /api/design-systems/install
Body: { "githubUrl": "https://github.com/..." }

# Import a local DESIGN.md (from a project directory)
POST /api/design-systems/import/local
Body: { "baseDir": "/absolute/path/to/project-dir", "name": "my-brand" }

# Delete a design system
DELETE /api/design-systems/:id
```

#### Skills

```bash
# List all skills
GET /api/skills

# Get a specific skill
GET /api/skills/:id

# List skill files
GET /api/skills/:id/files

# Get skill example HTML
GET /api/skills/:id/example

# Get skill asset
GET /api/skills/:id/assets/*

# Install a skill
POST /api/skills/install
Body: { "id": "my-skill", "content": "# Skill name\n..." }

# Import a skill
POST /api/skills/import
Body: { "name": "my-skill", "content": "..." }

# Update a skill
PUT /api/skills/:id
Body: { "content": "..." }

# Delete a skill
DELETE /api/skills/:id
```

#### Plugins

```bash
# List plugins
GET /api/plugins

# Get a plugin
GET /api/plugins/:id

# Install a plugin
POST /api/plugins/install
Body: { "id": "...", "version": "..." }

# Upload plugin as zip
POST /api/plugins/upload-zip

# Upload plugin as folder
POST /api/plugins/upload-folder

# Uninstall a plugin
POST /api/plugins/:id/uninstall

# Upgrade a plugin
POST /api/plugins/:id/upgrade

# Apply a plugin to current design
POST /api/plugins/:id/apply

# Trust a plugin
POST /api/plugins/:id/trust

# Doctor (diagnose plugin issues)
POST /api/plugins/:id/doctor
```

#### Projects

```bash
# Create a project
POST /api/projects
Body: { "name": "My Dashboard", "kind": "web" }

# List projects
GET /api/projects

# Get a project
GET /api/projects/:id

# List project files
GET /api/projects/:id/files

# Get a project file
GET /api/projects/:id/files/:path

# Upload a file
POST /api/projects/:id/files/:path

# Rename a file
POST /api/projects/:id/files/rename

# Create conversation
POST /api/projects/:id/conversations
Body: { "title": "Design discussion" }

# Get conversations
GET /api/projects/:id/conversations

# Get messages
GET /api/projects/:id/conversations/:cid/messages

# Post a comment
POST /api/projects/:id/conversations/:cid/comments

# Deploy project
POST /api/projects/:id/deploy

# Deploy preflight check
POST /api/projects/:id/deploy/preflight

# Generate media
POST /api/projects/:id/media/generate
Body: { "type": "image", "prompt": "..." }

# Export as PDF
POST /api/projects/:id/export/pdf

# Finalize for provider
POST /api/projects/:id/finalize/:provider
Body: { "anthropic": { ... } }

# Archive files
POST /api/projects/:id/archive/batch
```

#### Design System Templates

```bash
# List design templates
GET /api/design-templates

# Get a template
GET /api/design-templates/:id
```

#### Prompt Templates

```bash
# List prompt templates
GET /api/prompt-templates

# Get a prompt template
GET /api/prompt-templates/:surface/:id
```

#### Export

```bash
# Export applied plugins (design package)
POST /api/applied-plugins/export

# Prune applied plugins
POST /api/applied-plugins/prune

# Get applied plugins
GET /api/applied-plugins

# Get applied plugin snapshot
GET /api/applied-plugins/:snapshotId
```

## Common Workflows

### Workflow 1: Generate a Dashboard Design

```bash
# Step 1: Check available design systems
curl -s http://127.0.0.1:60479/api/design-systems | python3 -m json.tool

# Step 2: Create a design run
RUN_ID=$(curl -s -X POST http://127.0.0.1:60479/api/runs \
  -H "Content-Type: application/json" \
  -d '{"message": "创建一个三栏布局的 Agent 监控仪表板，包含 KPI 卡片、任务队列、实时指标图表", "designSystemId": "apple"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['runId'])")

# Step 3: Poll until complete
while true; do
  STATUS=$(curl -s http://127.0.0.1:60479/api/runs/$RUN_ID | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "Status: $STATUS"
  [ "$STATUS" != "running" ] && break
  sleep 3
done

# Step 4: Get run events for artifact
curl -s http://127.0.0.1:60479/api/runs/$RUN_ID/events
```

### Workflow 2: Import a Custom Design System

```bash
# Import from a project directory (must contain DESIGN.md or project files)
curl -s -X POST http://127.0.0.1:60479/api/design-systems/import/local \
  -H "Content-Type: application/json" \
  -d '{
    "baseDir": "/path/to/project-directory",
    "name": "dashboard-project"
  }'
```

### Workflow 3: Create Project + Generate Media

```bash
# Create project
PROJECT_ID=$(curl -s -X POST http://127.0.0.1:60479/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "Dashboard Project", "kind": "web"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Generate a hero image
curl -s -X POST http://127.0.0.1:60479/api/projects/$PROJECT_ID/media/generate \
  -H "Content-Type: application/json" \
  -d '{"type": "image", "prompt": "Apple-style dashboard UI mockup, clean minimal design"}'
```

### Workflow 4: Chat-based Design Generation (SSE)

```bash
# Stream generation via chat endpoint
curl -s -X POST http://127.0.0.1:60479/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Design a mobile app landing page with Apple aesthetics"}' \
  --no-buffer
```

## Helper Scripts

```bash
# Check daemon health
scripts/od-health.sh

# List design systems
scripts/od-list-systems.sh

# List skills
scripts/od-list-skills.sh

# List plugins
scripts/od-list-plugins.sh

# Create a design run and wait for completion
scripts/od-run.sh "Your design prompt here"

# Import a DESIGN.md file
scripts/od-import-system.sh path/to/DESIGN.md "system-name"

# Create a project
scripts/od-create-project.sh "Project Name" "web"
```

## Anti-Patterns

1. ❌ Don't hardcode the API base URL — use `http://127.0.0.1:60479`
2. ❌ Don't assume runs complete instantly — always poll `GET /api/runs/:id`
3. ❌ Don't ignore SSE events — they contain the generated artifacts
4. ❌ Don't skip health check before calling other endpoints
5. ❌ Don't use random design system IDs — check `GET /api/design-systems` first

## Error Handling

| Status Code | Meaning | Action |
|-------------|---------|--------|
| 200 | Success | Parse response |
| 202 | Accepted (async) | Poll for completion |
| 400 | Bad Request | Check request body format |
| 404 | Not Found | Verify resource ID |
| 409 | Conflict | Resource already exists or requires different path |
| 503 | Daemon shutting down | Restart daemon |
| 501 | Not Implemented | Feature not available in current version |

## Notes

- All endpoints return JSON unless otherwise noted
- SSE endpoints (`/api/chat`, `/api/runs/:id/events`) stream text/event-stream
- The daemon stores data in SQLite — state persists across restarts
- Version: 0.7.0 (as of 2026-05)
- Source: https://github.com/nexu-io/open-design
