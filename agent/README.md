# Registry Agent (OpenAI Agents SDK)

A CLI agent that uses your **MCP Registry catalog** as its tool source. You pick
which servers (or specific tools) from the catalog, and the agent connects to them
through the registry's per-server MCP endpoints and runs a chat loop.

```
  catalog (registry)          you pick            agent loop
  ┌───────────────┐      ┌──────────────┐    ┌──────────────────┐
  │ Orders         │      │ orders        │    │ OpenAI Agents SDK │
  │ Inventory      │ ───▶ │ inventory     │──▶ │  (LLM + tools)    │──▶ calls tools
  │ PR Agent (BBS) │      │ pr_agent...   │    │                   │     via registry
  └───────────────┘      └──────────────┘    └──────────────────┘
```

## Run

```bash
cd agent
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export OPENAI_API_KEY=sk-...        # the agent's brain
export REGISTRY_URL=http://localhost:8000   # optional
export REGISTRY_USER=vikas                  # optional (identity in /mcp/<user>/...)
export AGENT_MODEL=gpt-4o                    # optional

python agent_cli.py
```

You'll see the catalog, then a prompt:

```
=== Catalog ===
  [0] Orders  (orders)
        orders__get_order_status, orders__list_orders_for_customer
  [1] Inventory  (inventory)
        inventory__check_stock, inventory__list_low_stock

Select: server numbers (e.g. 0,2), 'all', and/or specific tool names
(e.g. orders__get_order_status):
```

Selection rules:
- `all` — every active server
- `0,1` — those servers (all their tools)
- `orders__get_order_status` — just that one tool (uses the SDK's static tool filter)
- mix freely, comma-separated

Then chat:

```
you> what's the status of order A-1001?
agent> Order A-1001 is shipped (total $49.0).
```

## How it connects

For each selection it builds an `MCPServerStreamableHttp` pointing at
`<registry>/mcp/<user>/<slug>`, optionally with `create_static_tool_filter(...)`
for specific tools, and passes them as `mcp_servers=[...]` to an `Agent`. The agent
auto-discovers the tools and calls them during `Runner.run(...)`.

> The registry stays the single source of truth: connect/disconnect or publish new
> servers in the registry and the agent picks them up on the next launch.

## Invoke API (call a saved agent from other systems)

Run the web service (`uvicorn web:app --port 8800`) and POST to a saved agent by
**name or id**:

```bash
# one-shot
curl -X POST "http://localhost:8800/v1/agents/API%20Demo/invoke" \
  -H 'Content-Type: application/json' \
  -d '{"message":"Is order A-1001 shipped?"}'
# → {"agent":"API Demo","conversation_id":"…","tools":[…],"reply":"Order A-1001 has been shipped."}

# multi-turn: reuse a conversation_id to keep memory
curl -X POST "http://localhost:8800/v1/agents/API%20Demo/invoke" \
  -H 'Content-Type: application/json' \
  -d '{"message":"And the status of the first one?","conversation_id":"sess-42"}'
```

Request body: `{ "message": str, "user"?: str="vikas", "conversation_id"?: str }`.
Omit `conversation_id` for a stateless one-shot (a fresh id is returned); reuse it
to continue a conversation.

**Auth:** set `AGENT_API_KEY=…` on the service to require it — callers then send
`X-API-Key: …`. If unset, the API is open (dev only).

The built agent (its MCP connections) is cached per agent id and rebuilt
automatically when you edit that agent's prompt/tools/model in the registry.
