"""Fivetran MCP stdio client — wraps the official `fivetran/fivetran-mcp` server.

This is the REAL Model Context Protocol integration for the Fivetran track. It spawns
the official open-source Fivetran MCP server (OpenAPI-generated, 50+ tools) over stdio
and calls its tools via the MCP protocol.

`agent/tools/fivetran_mcp.py` uses these calls on the read path (list_connections,
get_connection_details) with a direct-REST fallback, so the live demo never depends on
the subprocess succeeding — but when it does, the control-plane data genuinely flows
through the Fivetran MCP server.

Server launch + auth verified against fivetran/fivetran-mcp@main:
  - entry: `python server.py` (stdio transport)
  - auth env: FIVETRAN_API_KEY, FIVETRAN_API_SECRET
  - write gate: FIVETRAN_ALLOW_WRITES (we force "false" — read path only)
"""

from __future__ import annotations

import json
import os
from typing import Any

import config

# Path to the cloned fivetran-mcp server.py inside the image (see Dockerfile).
_SERVER_PATH = os.environ.get("FIVETRAN_MCP_SERVER", "/opt/fivetran-mcp/server.py")


def _server_env() -> dict[str, str]:
    env = dict(os.environ)
    try:
        env["FIVETRAN_API_KEY"] = config.fivetran_api_key()
        env["FIVETRAN_API_SECRET"] = config.fivetran_api_secret()
    except Exception:
        pass
    # Read path only — never allow writes through the spawned MCP server.
    env["FIVETRAN_ALLOW_WRITES"] = "false"
    return env


def _params():
    from mcp.client.stdio import StdioServerParameters

    return StdioServerParameters(
        command="python",
        args=[_SERVER_PATH],
        env=_server_env(),
    )


async def call_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Open an MCP session, call one tool, return parsed JSON (or raw text/None)."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    async with stdio_client(_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments or {})
            if result.content:
                content = result.content[0]
                text = getattr(content, "text", None)
                if text is not None:
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return text
            return None


async def list_tool_names() -> list[str]:
    """Return the names of every tool the Fivetran MCP server exposes (verification)."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    async with stdio_client(_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return [t.name for t in tools.tools]


def extract_items(result: Any) -> list[dict] | None:
    """Normalize a Fivetran MCP tool result into a list of items (or None if unparseable)."""
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        data = result.get("data", result)
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data, list):
            return data
    return None


def extract_data(result: Any) -> dict | None:
    """Normalize a Fivetran MCP tool result into the `data` object (or None)."""
    if isinstance(result, dict):
        data = result.get("data", result)
        if isinstance(data, dict):
            return data
    return None
