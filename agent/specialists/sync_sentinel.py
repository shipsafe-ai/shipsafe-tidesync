from typing import Any

from agent.tools import fivetran_mcp


class SyncSentinel:
    """Queries Fivetran MCP for pipeline control-plane truth."""

    async def run(self) -> list[dict[str, Any]]:
        connections = await fivetran_mcp.list_connections()
        if not connections:
            return []

        reports = []
        for conn in connections:
            conn_id = conn["id"]
            details = await fivetran_mcp.get_connection_details(conn_id)

            # Fivetran returns status as a dict; tests may mock it as a plain string
            status_raw = details.get("status", conn.get("status", {}))
            if isinstance(status_raw, dict):
                setup_state = status_raw.get("setup_state", "unknown")
                sync_state = status_raw.get("sync_state")
            else:
                setup_state = status_raw
                sync_state = None

            reports.append({
                "connection_id": conn_id,
                "status": setup_state,
                "succeeded_at": details.get("succeeded_at"),
                "failed_at": details.get("failed_at"),
                "sync_frequency": details.get("sync_frequency"),
                "row_count": details.get("row_count", 0),
                "destination_id": details.get("destination_id"),
                "group_id": details.get("group_id"),
                "sync_state": sync_state,
                "setup_state": setup_state,
                "schema": details.get("schema"),
                "service": details.get("service"),
                "paused": details.get("paused", False),
            })

        return reports
