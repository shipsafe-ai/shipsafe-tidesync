import pytest
from unittest.mock import AsyncMock, patch
from conftest import MOCK_CONNECTION, MOCK_FIVETRAN_REPORT


@pytest.mark.asyncio
async def test_sync_sentinel_returns_fivetran_report():
    from agent.specialists.sync_sentinel import SyncSentinel

    sentinel = SyncSentinel()
    with patch("agent.tools.fivetran_mcp.list_connections", new_callable=AsyncMock) as mock_list, \
         patch("agent.tools.fivetran_mcp.get_connection_details", new_callable=AsyncMock) as mock_detail:

        mock_list.return_value = [MOCK_CONNECTION]
        mock_detail.return_value = {
            **MOCK_CONNECTION,
            "row_count": 1_200_000,
            "destination_id": "dest_bq1",
            "status": {"setup_state": "connected", "sync_state": "scheduled"},
        }

        reports = await sentinel.run()

    assert len(reports) == 1
    r = reports[0]
    assert r["connection_id"] == "conn_abc123"
    assert r["status"] == "connected"
    assert r["succeeded_at"] == "2026-06-07T09:14:00Z"
    assert r["sync_frequency"] == 60


@pytest.mark.asyncio
async def test_sync_sentinel_handles_failed_connection():
    from agent.specialists.sync_sentinel import SyncSentinel

    failed = {**MOCK_CONNECTION, "status": "broken", "failed_at": "2026-06-07T08:00:00Z"}
    sentinel = SyncSentinel()
    with patch("agent.tools.fivetran_mcp.list_connections", new_callable=AsyncMock) as mock_list, \
         patch("agent.tools.fivetran_mcp.get_connection_details", new_callable=AsyncMock) as mock_detail:

        mock_list.return_value = [failed]
        mock_detail.return_value = {
            **failed,
            "row_count": 0,
            "destination_id": "dest_bq1",
            "status": {"setup_state": "broken", "sync_state": "error"},
        }

        reports = await sentinel.run()

    assert reports[0]["status"] == "broken"
    assert reports[0]["failed_at"] == "2026-06-07T08:00:00Z"


@pytest.mark.asyncio
async def test_sync_sentinel_empty_connections():
    from agent.specialists.sync_sentinel import SyncSentinel

    sentinel = SyncSentinel()
    with patch("agent.tools.fivetran_mcp.list_connections", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = []
        reports = await sentinel.run()

    assert reports == []
