# Setup — from zero to running

End-to-end local setup: the registry, MongoDB, an MCP server, the web UI, and
(optionally) the agent service.

## Quick start (one command)

On a machine with **Python 3.13** and **MongoDB running** (`brew services start
mongodb-community@7.0` or `docker run -d -p 27017:27017 mongo:7`):

```bash
git clone https://github.com/vikas-arc/mcp-registry.git
cd mcp-registry
./scripts/dev-up.sh        # creates venv, starts registry + Atlassian MOCK, publishes it
# → open http://localhost:8000/ui/
./scripts/dev-down.sh      # stop everything
```

`dev-up.sh` brings it up with a **mock** Atlassian server (no credentials), so you can
see it working immediately. Swap in the real servers using the steps below. For the
manual / production path, read on.

## 0. Prerequisites

- **Python 3.13** (the MCP SDK needs ≥3.10; 3.13 used here)
- **MongoDB** — local (`brew install mongodb-community@7.0`), Docker, or Atlas
- **uv** (for `uvx`, to run mcp-atlassian) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **git**

## 1. Clone + Python environment

```bash
git clone https://github.com/vikas-arc/mcp-registry.git
cd mcp-registry
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Start MongoDB

```bash
# option A — Homebrew
brew services start mongodb-community@7.0
# option B — Docker
docker run -d --name mongo -p 27017:27017 mongo:7
# option C — Atlas: nothing to run; copy your SRV URI for step 3
```

## 3. Configure

```bash
cp .env.example .env
```
Edit `.env`:
```
MONGO_URL=mongodb://localhost:27017      # or your Atlas SRV URI
MONGO_DB=mcp_registry
ALLOW_PRIVATE_NETWORKS=true              # needed for localhost MCP servers in dev
```

## 4. Run the registry

```bash
uvicorn app.main:app --reload            # http://localhost:8000  (UI at /ui/, docs at /docs)
```
Health check: `curl localhost:8000/health` → `{"status":"ok"}`.

## 5. Run an MCP server

Each server is its **own process** (own terminal / background / Docker), started
separately from the registry, and must be reachable from it. Each lives in its own
folder under `servers/` (or `examples/` for the credential-free demos).

**Quick test (no creds) — Atlassian mock:**
```bash
ATL_MODE=all ATL_PORT=9004 python examples/atlassian_mock.py    # http://127.0.0.1:9004/mcp
```

**Real Atlassian (Jira + Confluence Server/DC) — `servers/atlassian/`:**
1. Create a **read-only** Personal Access Token in Jira (avatar → Profile → Personal
   Access Tokens) and another in Confluence.
2. Install, configure, run (the host must reach your Jira/Confluence URLs):
   ```bash
   cd servers/atlassian
   ./install.sh                       # venv + mcp-atlassian
   cp .env.example .env               # fill JIRA_URL / tokens / CONFLUENCE_URL
   ./.venv/bin/python server.py       # http://127.0.0.1:9004/mcp
   ```
   (Set `JIRA_SSL_VERIFY=false` / `CONFLUENCE_SSL_VERIFY=false` in `.env` for self-signed certs.)

**Real PR-Agent (Bitbucket Server) — `servers/pr_agent_bitbucket/`:**
```bash
cd servers/pr_agent_bitbucket
./install.sh                          # pr-agent, then mcp (two-step)
cp .env.example .env                  # fill BITBUCKET_SERVER_URL / token / OPENAI_KEY
./.venv/bin/python server.py          # http://127.0.0.1:9003/mcp
```

> Each server runs on its own port — give them distinct `ATL_PORT`/ports if you run
> several. Use separate terminals, or background them (`nohup … &`) / Docker / systemd.

## 6. Publish the server to the catalog

```bash
curl -X POST localhost:8000/catalog -H 'Content-Type: application/json' \
  -d '{"name":"Atlassian","base_url":"http://127.0.0.1:9004/mcp","transport":"http","forward_auth":true}'
```
- `forward_auth: true` → caller's token is passed through (bring-your-own-token).
- `status: active` with a tool count > 0 means it handshook fine. **0 tools** = the
  server couldn't reach/authenticate Atlassian (check creds / network), not a registry bug.

## 7. Use it

- Open **http://localhost:8000/ui/** → see the server, its tools, and **Connect** it.
- Copy your personal endpoint (`http://localhost:8000/mcp/<you>`) into an editor:
  - **Claude Code:** `claude mcp add --transport http team-registry http://localhost:8000/mcp/<you>`
  - **Copilot** `.vscode/mcp.json` / **Cursor** / **Windsurf**: see the snippets in the UI.

## 8. (Optional) Agent service

```bash
cd agent
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...           # or another provider
export REGISTRY_URL=http://localhost:8000
uvicorn web:app --port 8800            # http://localhost:8800
```
Build/save/run agents over the catalog tools; for 🔑 (forward_auth) servers, paste
your token in the per-server field (never stored).

## Common issues

| Symptom | Cause / fix |
| --- | --- |
| Publish returns `status: error` | Registry can't reach the server URL, or SSRF blocked it (set `ALLOW_PRIVATE_NETWORKS=true` for localhost). |
| Atlassian published but **0 tools** | mcp-atlassian couldn't auth/reach Jira/Confluence — check PATs, URLs, VPN, `-v` logs. |
| `address already in use` on 9004 | Another server (e.g. the mock) is on that port: `kill $(lsof -ti:9004)`. |
| Agent chat → `OPENAI_API_KEY is not set` | Export the key before starting the agent service. |
