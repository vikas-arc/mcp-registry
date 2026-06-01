# MCP Registry

A team **catalog + gateway** for custom MCP servers.

- **You (admin)** publish your custom MCP servers to a shared catalog.
- **Teammates** browse the catalog, pick the servers they want, and connect them.
- Each teammate gets a personal MCP endpoint (`/mcp/<user_id>`) they plug into
  **GitHub Copilot** (or Claude, Cursor, …) — and see exactly the tools they chose.

> No auth yet (by design, for now). A teammate is identified by the `X-User-Id`
> header on the REST API and by the `<user_id>` path segment on the MCP endpoint.
> Swap both for real auth before exposing this.

## How it fits together

```
  ADMIN ──POST /catalog──▶  ┌──────────── Catalog ────────────┐
  (your custom servers)     │ 🟪 Orders  🟦 Inventory  🟨 Reports│  every teammate sees this
                            └──────────────┬───────────────────┘
  TEAMMATE ──GET /catalog──▶ browse        │
           ──POST /me/connections──▶ pick the ones they want
                                           │
  GitHub Copilot ──connect /mcp/<user>──▶ registry re-exposes ONLY their picks
                                           │
                                           ▼ routes each call upstream
                              🟪 Orders   🟦 Inventory   🟨 Reports
```

Two layers:

| Layer | Managed by | MongoDB collection |
| --- | --- | --- |
| **Catalog** — master list of custom servers | admin | `catalog` (each server's tools embedded) |
| **Connections** — which servers a teammate picked | each teammate | `connections` |
| **Agents** — saved custom agents | each teammate | `agents` |

Persistence is **MongoDB** (via `motor`). Servers, connections, and saved agents
survive restarts.

Tools are namespaced `slug__tool_name` (e.g. `orders__get_order_status`) so two
servers can share a tool name without clashing.

## API

REST endpoints take an `X-User-Id` header (auth stub — see `app/deps.py`).

| Method | Path | Who | Purpose |
| --- | --- | --- | --- |
| POST | `/catalog` | admin | Publish a custom server (handshakes + caches its tools) |
| GET | `/catalog` | anyone | Browse all servers (with a `connected` flag) |
| GET | `/catalog/{id}/tools` | anyone | Tools a server exposes |
| POST | `/catalog/{id}/refresh` | admin | Re-handshake + refresh cached tools |
| DELETE | `/catalog/{id}` | admin | Remove from catalog |
| POST | `/me/connections` | teammate | Connect a catalog server (`{ "catalog_id": ... }`) |
| GET | `/me/connections` | teammate | List what you've connected |
| DELETE | `/me/connections/{catalog_id}` | teammate | Disconnect |
| GET | `/gateway/tools` | teammate | Your aggregated namespaced tools (REST) |
| POST | `/gateway/tools/call` | teammate | Call a tool (REST, for testing) |
| — | `/mcp/{user_id}` | MCP client | **The endpoint Copilot/Claude/Cursor connect to** |

## Run it end-to-end

> Needs **Python 3.10+** (the MCP SDK requires it). Your system `python3` may be older.

```bash
cd ~/Workspace/mcp-registry
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # for local testing set ALLOW_PRIVATE_NETWORKS=true
docker compose up -d db       # MongoDB; or point MONGO_URL at your own
```

**1. Start a sample custom server** (stands in for one of your real ones):
```bash
python examples/sample_server.py        # streamable HTTP at http://127.0.0.1:9001/mcp
```

**2. Start the registry:**
```bash
uvicorn app.main:app --reload            # http://localhost:8000  (docs at /docs)
```

**3. Admin publishes it to the catalog:**
```bash
curl -X POST localhost:8000/catalog -H 'Content-Type: application/json' \
  -d '{"name":"Orders","base_url":"http://127.0.0.1:9001/mcp","transport":"http"}'
```

**4. A teammate ("alice") browses and connects it:**
```bash
curl localhost:8000/catalog -H 'X-User-Id: alice'           # see Orders in the list
# copy its id, then:
curl -X POST localhost:8000/me/connections -H 'X-User-Id: alice' \
  -H 'Content-Type: application/json' -d '{"catalog_id":"<ID-FROM-ABOVE>"}'
```

**5a. Verify via REST:**
```bash
curl localhost:8000/gateway/tools -H 'X-User-Id: alice'
curl -X POST localhost:8000/gateway/tools/call -H 'X-User-Id: alice' \
  -H 'Content-Type: application/json' \
  -d '{"namespaced_name":"orders__get_order_status","arguments":{"order_id":"A-1001"}}'
```

**5b. Or connect from GitHub Copilot** — add to `.vscode/mcp.json`:
```json
{
  "servers": {
    "team-registry": {
      "type": "http",
      "url": "http://localhost:8000/mcp/alice"
    }
  }
}
```
Copilot agent mode now lists `orders__get_order_status` and friends — only the
servers alice connected.

## Web UI

A minimal browse-and-connect page is served at **http://localhost:8000/ui/**:

- A "you are …" box (no auth yet) to act as any teammate — switch it to see how
  each person's connected set differs.
- Each catalog server shows its tools and a **Connect / Disconnect** button.
- Your personal MCP endpoint (`/mcp/<you>`) is shown at the top to copy into
  Copilot / Claude / Cursor.
- An admin row at the bottom to publish a new server to the catalog.

## Two sample servers

`examples/sample_server.py` (Orders, :9001) and `examples/inventory_server.py`
(Inventory, :9002) let you demo teammates picking different subsets — e.g. vikas
connects Orders, alice connects Inventory, and each `/mcp/<user>` exposes only
their picks.

## Before production — TODO

- **Real auth** — replace the `X-User-Id` header and `/mcp/{user_id}` path with a
  verified token; derive the user from it.
- **Per-server credentials** — when your custom servers need auth, store per-user
  tokens encrypted (the `crypto.py` / SSRF scaffolding is already here).
- **MongoDB indexes** (e.g. unique `slug` on `catalog`, `(user_id, catalog_id)` on `connections`, `(user_id, name)` on `agents`) + auth on the Mongo instance.
- **Egress lockdown / pinned-IP transport** to fully close DNS-rebinding SSRF.
- **MCP session pooling** in `app/mcp/client.py` (currently one session per call).
- **Per-user rate limiting** on tool calls.
```
