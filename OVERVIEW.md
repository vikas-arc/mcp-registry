# MCP Registry — System Overview

A team platform for custom MCP servers: an **admin-curated catalog**, a **per-user
gateway** that re-exposes each person's chosen tools as a single MCP endpoint, and a
**no-code agent builder** that runs LLM agents over those tools.

## Services

| Service | Tech | Port | Role |
| --- | --- | --- | --- |
| **Registry** | FastAPI + MongoDB (motor) | 8000 | Catalog, per-user connections, saved agents, gateway, `/mcp` endpoints, web UI (`/ui/`) |
| **Agent service** | FastAPI + OpenAI Agents SDK | 8800 | Agent builder/chat UI + invoke REST API |
| **PR Agent (Bitbucket Server)** | FastMCP wrapping qodo-ai/pr-agent | 9003 | review/describe/improve/ask/update_changelog/add_docs |
| **Atlassian** | `ghcr.io/sooperset/mcp-atlassian` | 9004 | Jira + Confluence (single multi-user instance) |
| **MongoDB** | Atlas (prod) / local | 27017 | Persistence |

## Data model (MongoDB collections)

- `catalog` — published servers; **tools embedded** in each doc. Fields incl. `slug`, `base_url`, `transport`, `status`, `forward_auth`.
- `connections` — `{user_id, catalog_id, enabled}`: which servers a teammate picked.
- `agents` — `{user_id, name, instructions, selection[], model}`: saved custom agents.

## How the pieces connect

```
editors / agents ──(MCP over HTTP)──▶  Registry  ──(by URL)──▶  custom MCP servers
                                          │                       (Atlassian, PR-Agent, …)
   /mcp/<user>            aggregate: all servers the user connected
   /mcp/<user>/<slug>     single server
                                          └── MongoDB (catalog · connections · agents)

Agent service ──(MCP)──▶ Registry ──▶ servers      (chat UI + POST /v1/agents/{ref}/invoke)
```

## Key capabilities (all built + verified)

- **Catalog**: admin publishes servers (`POST /catalog`); handshake caches tools; browse with per-user `connected` flag.
- **Connect**: teammates pick servers (`/me/connections`) → feeds the aggregate endpoint.
- **Two endpoint shapes**: aggregate `/mcp/<user>` and single `/mcp/<user>/<slug>`. Tools namespaced `slug__tool`.
- **Editors**: per-server snippets for Claude Code, VS Code Copilot, Windsurf, Cursor.
- **Agents**: build (name + system prompt + tool selection + model), **save**, **run** (chat), or call via **invoke API**. Conversation memory per session.
- **BYOT auth pass-through**: servers flagged `forward_auth: true` receive the caller's `Authorization` token (forwarded by the registry / agent service); `shared` servers never do. Agent builder collects **per-server tokens** (never persisted).
- **Atlassian model**: one instance + read-only shared service account fallback; a user's forwarded PAT takes precedence → reads shared, writes/personal as the user.

## Deployment (AWS EKS)

`k8s/` has namespace, config, secrets template, Deployments+Services (registry, agent,
pr-agent, atlassian), and an ALB Ingress (registry + agent exposed; MCP servers internal).
Build registry/agent/pr-agent images to ECR; atlassian uses the public image. MongoDB → Atlas.
See `k8s/README.md` for the full runbook.

## Repo layout

```
app/                      registry (FastAPI + motor)
  routers/ services/ mcp/ security/ static/index.html  mcp_server.py
agent/                    agent service (web.py, agent_cli.py, static/chat.html, Dockerfile)
servers/pr_agent_bitbucket/   PR-Agent MCP server (server.py, install.sh, Dockerfile)
examples/                 sample_server.py, inventory_server.py, atlassian_mock.py
k8s/                      EKS manifests + README
Dockerfile docker-compose.yml requirements.txt README.md
```

## Before production — must-dos

1. **🚨 Real authentication.** Replace the `X-User-Id` header / `/mcp/<user>` path identity
   (`app/deps.py`) with verified JWT/SSO. THE launch blocker — without it anyone can impersonate anyone.
2. **SSRF allowlist.** In-cluster needs `ALLOW_PRIVATE_NETWORKS=true`; tighten to an allowlist of the
   MCP Service DNS names so arbitrary private URLs can't be published.
3. **Mongo indexes**: unique `slug` (catalog), `(user_id, catalog_id)` (connections), `(user_id, name)` (agents).
4. **Atlassian service account = read-only** in Jira/Confluence (enforces the read/write split).
5. **Real creds + rotate**: Atlassian service PAT, Bitbucket token, OpenAI key (rotate the one pasted during dev).
6. **Replace the Atlassian mock** with the real `mcp-atlassian` instance.
7. **Scaling**: shared session store before running the agent service >1 replica; HPA; NetworkPolicies.
