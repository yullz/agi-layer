"""MCP server — expose the layer as tools other agents can call.

This is what makes the layer the *bridge*: publish memory + routing as MCP
tools so external agents — including an OpenClaw-style setup — connect to
this as their shared memory-and-routing hub.
"""
from __future__ import annotations


def build_mcp_server(store, orchestrator):
    """Register tools:
        ask(input, scope)        -> route through the full turn loop
        retrieve_memory(query)   -> read-only memory search
        remember(fact, scope)    -> write a durable memory item
    """
    raise NotImplementedError("Wire the MCP server; see ARCHITECTURE.md (Interfaces)")
