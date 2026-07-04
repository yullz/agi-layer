"""MCP server — expose the layer as tools other agents can call.

This is what makes the layer the *bridge*: publish memory + routing as MCP tools
so external agents (an OpenClaw-style setup, other assistants) connect to this as
their shared memory-and-routing hub. Requires `pip install mcp`.

Run:  AGI_INTERFACE=mcp python main.py
"""
from __future__ import annotations

from core.session import Session
from memory.schema import Turn


def build_mcp_server(store, orchestrator):
    """Build a FastMCP server exposing ask / retrieve_memory / remember."""
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as e:  # pragma: no cover - depends on install
        raise RuntimeError(
            "The MCP SDK isn't installed — `pip install mcp` to run the bridge."
        ) from e

    server = FastMCP("agi-layer")

    @server.tool()
    def ask(input: str, scope: str | None = None) -> str:
        """Route a message through the full turn loop (memory + model)."""
        return orchestrator.handle_turn(input, Session(scope=scope))

    @server.tool()
    def retrieve_memory(query: str, scope: str | None = None,
                        budget_tokens: int = 2000) -> list:
        """Read-only memory search — returns the packed memory contents."""
        bundle = store.retrieve(query, scope=scope, budget_tokens=budget_tokens)
        return [c.content for c in bundle.items]

    @server.tool()
    def remember(fact: str, scope: str | None = None) -> str:
        """Write a durable memory item (reconciled + graph-linked)."""
        store.remember(fact, scope=scope)
        return "remembered"

    return server
