"""A sample custom MCP server with custom tools.

This stands in for one of YOUR real custom servers. Run it, then publish it to the
registry catalog and any teammate can connect it.

    pip install mcp
    python examples/sample_server.py
    # serves streamable HTTP at  http://127.0.0.1:9001/mcp

Then publish to the registry:

    curl -X POST localhost:8000/catalog -H 'Content-Type: application/json' \
      -d '{"name": "Orders", "base_url": "http://127.0.0.1:9001/mcp", "transport": "http"}'

(For local testing the registry must allow private addresses — set
 ALLOW_PRIVATE_NETWORKS=true in its .env.)
"""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Orders", host="127.0.0.1", port=9001)

# Fake data so the tools return something.
_ORDERS = {
    "A-1001": {"status": "shipped", "customer": "alice", "total": 49.0},
    "A-1002": {"status": "processing", "customer": "bob", "total": 12.5},
}


@mcp.tool()
def get_order_status(order_id: str) -> str:
    """Return the current status of an order by its ID."""
    order = _ORDERS.get(order_id)
    if order is None:
        return f"No order found with id {order_id}"
    return f"Order {order_id} is {order['status']} (total ${order['total']})."


@mcp.tool()
def list_orders_for_customer(customer: str) -> list[str]:
    """List all order IDs belonging to a given customer."""
    return [oid for oid, o in _ORDERS.items() if o["customer"] == customer]


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
