import base64

import httpx

import config

BASE = "https://api.fivetran.com/v1"
_TIMEOUT = 30.0


def _auth() -> str:
    key = config.fivetran_api_key()
    secret = config.fivetran_api_secret()
    creds = f"{key}:{secret}"
    return "Basic " + base64.b64encode(creds.encode()).decode()


def _headers() -> dict:
    return {"Authorization": _auth(), "Content-Type": "application/json"}


def _require_writes() -> None:
    if not config.FIVETRAN_ALLOW_WRITES:
        raise PermissionError("Write operations disabled. Set FIVETRAN_ALLOW_WRITES=true")


# ── Read operations ────────────────────────────────────────────────────────────
#
# Control-plane reads go through the official Fivetran MCP server first
# (agent/tools/fivetran_mcp_client.py → fivetran/fivetran-mcp over stdio). If the
# MCP path is unavailable for any reason, they fall back to direct Fivetran REST so
# the demo never breaks. USE_FIVETRAN_MCP=false disables the MCP path entirely.

import os as _os


def _mcp_enabled() -> bool:
    return _os.environ.get("USE_FIVETRAN_MCP", "true").lower() == "true"


async def list_connections(limit: int = 100) -> list[dict]:
    if _mcp_enabled():
        try:
            from agent.tools import fivetran_mcp_client
            result = await fivetran_mcp_client.call_tool("list_connections", {"limit": limit})
            items = fivetran_mcp_client.extract_items(result)
            if items is not None:
                return items
        except Exception:
            pass  # fall through to REST
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{BASE}/connections", headers=_headers(), params={"limit": limit})
        resp.raise_for_status()
        return resp.json().get("data", {}).get("items", [])


async def get_connection_details(connection_id: str) -> dict:
    if _mcp_enabled():
        try:
            from agent.tools import fivetran_mcp_client
            result = await fivetran_mcp_client.call_tool(
                "get_connection_details", {"connection_id": connection_id}
            )
            data = fivetran_mcp_client.extract_data(result)
            if data:
                return data
        except Exception:
            pass  # fall through to REST
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{BASE}/connections/{connection_id}", headers=_headers())
        resp.raise_for_status()
        return resp.json().get("data", {})


async def get_connection_state(connection_id: str) -> dict:
    # Fivetran has no /state endpoint — state lives in connection details under "status"
    details = await get_connection_details(connection_id)
    return details.get("status", {})


async def get_connection_schema_config(connection_id: str) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{BASE}/connections/{connection_id}/schemas", headers=_headers())
        resp.raise_for_status()
        return resp.json().get("data", {})


async def list_destinations() -> list[dict]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{BASE}/destinations", headers=_headers())
        resp.raise_for_status()
        return resp.json().get("data", {}).get("items", [])


async def list_webhooks() -> list[dict]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{BASE}/webhooks", headers=_headers())
        resp.raise_for_status()
        return resp.json().get("data", {}).get("items", [])


async def get_webhook_details(webhook_id: str) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{BASE}/webhooks/{webhook_id}", headers=_headers())
        resp.raise_for_status()
        return resp.json().get("data", {})


async def get_group_service_account(group_id: str) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{BASE}/groups/{group_id}/service-account", headers=_headers())
        resp.raise_for_status()
        return resp.json().get("data", {})


# ── Write operations (gated) ───────────────────────────────────────────────────

async def run_connection_setup_tests(connection_id: str) -> dict:
    _require_writes()
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{BASE}/connections/{connection_id}/test", headers=_headers())
        resp.raise_for_status()
        return resp.json().get("data", {})


async def sync_connection(connection_id: str) -> dict:
    _require_writes()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{BASE}/connections/{connection_id}/sync", headers=_headers())
        resp.raise_for_status()
        return resp.json().get("data", {})


async def resync_connection(connection_id: str) -> dict:
    _require_writes()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{BASE}/connections/{connection_id}/resync", headers=_headers())
        resp.raise_for_status()
        return resp.json().get("data", {})


async def create_account_webhook(url: str, events: list[str], secret: str) -> dict:
    _require_writes()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{BASE}/webhooks/account",
            headers=_headers(),
            json={"url": url, "events": events, "secret": secret, "active": True},
        )
        resp.raise_for_status()
        return resp.json().get("data", {})


async def test_webhook(webhook_id: str) -> dict:
    _require_writes()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{BASE}/webhooks/{webhook_id}/test", headers=_headers())
        resp.raise_for_status()
        return resp.json().get("data", {})
