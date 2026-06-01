"""A second sample custom MCP server — Inventory — with its own custom tools.

Run alongside the Orders server to demonstrate teammates picking different subsets.

    python examples/inventory_server.py     # streamable HTTP at http://127.0.0.1:9002/mcp
"""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Inventory", host="127.0.0.1", port=9002)

_STOCK = {
    "widget": 42,
    "gadget": 3,
    "gizmo": 0,
}


@mcp.tool()
def check_stock(sku: str) -> str:
    """Return how many units of a SKU are in stock."""
    if sku not in _STOCK:
        return f"Unknown SKU: {sku}"
    return f"{sku}: {_STOCK[sku]} in stock"


@mcp.tool()
def list_low_stock(threshold: int = 5) -> list[str]:
    """List SKUs at or below the given stock threshold."""
    return [sku for sku, qty in _STOCK.items() if qty <= threshold]


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
