import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from conftest import MOCK_BQ_REPORT


@pytest.mark.asyncio
async def test_data_doctor_returns_bq_report():
    from agent.specialists.data_doctor import DataDoctor

    doctor = DataDoctor()
    with patch("agent.tools.bigquery_client.query_freshness", new_callable=AsyncMock) as mock_q, \
         patch("agent.tools.fivetran_mcp.get_connection_schema_config", new_callable=AsyncMock) as mock_schema:

        mock_schema.return_value = {"schemas": {"hormuz_port_arrivals": {"tables": {"arrivals": {"enabled": True}}}}}
        mock_q.return_value = MOCK_BQ_REPORT

        reports = await doctor.run(connection_id="conn_abc123")

    assert len(reports) == 1
    r = reports[0]
    assert r["table"] == "arrivals"
    assert r["lag_seconds"] == 16_740
    assert r["row_count"] == 1_200_000


@pytest.mark.asyncio
async def test_data_doctor_detects_staleness():
    from agent.specialists.data_doctor import DataDoctor

    stale = {**MOCK_BQ_REPORT, "lag_seconds": 16_740}  # > 3600s threshold
    doctor = DataDoctor()
    with patch("agent.tools.bigquery_client.query_freshness", new_callable=AsyncMock) as mock_q, \
         patch("agent.tools.fivetran_mcp.get_connection_schema_config", new_callable=AsyncMock) as mock_schema:

        mock_schema.return_value = {"schemas": {"hormuz_port_arrivals": {"tables": {"arrivals": {"enabled": True}}}}}
        mock_q.return_value = stale

        reports = await doctor.run(connection_id="conn_abc123")

    assert reports[0]["lag_seconds"] > 3600


@pytest.mark.asyncio
async def test_data_doctor_null_rate_drift():
    from agent.specialists.data_doctor import DataDoctor

    high_null = {**MOCK_BQ_REPORT, "null_rates": {"vessel_name": 0.45, "timestamp": 0.0}}
    doctor = DataDoctor()
    with patch("agent.tools.bigquery_client.query_freshness", new_callable=AsyncMock) as mock_q, \
         patch("agent.tools.fivetran_mcp.get_connection_schema_config", new_callable=AsyncMock) as mock_schema:

        mock_schema.return_value = {"schemas": {"hormuz_port_arrivals": {"tables": {"arrivals": {"enabled": True}}}}}
        mock_q.return_value = high_null

        reports = await doctor.run(connection_id="conn_abc123")

    assert reports[0]["null_rates"]["vessel_name"] == 0.45
