import pytest
from unittest.mock import patch
from conftest import MOCK_FIVETRAN_REPORT, MOCK_BQ_REPORT

MOCK_BRIEFING = {
    "summary": "1 connection healthy, 0 stale. No action needed.",
    "connections_ok": 1,
    "anomalies": [],
    "actions_taken": [],
    "generated_at": "2026-06-07T09:00:00Z",
}


@pytest.mark.asyncio
async def test_briefing_agent_returns_briefing():
    from agent.specialists.briefing_agent import BriefingAgent

    agent = BriefingAgent()
    with patch.object(agent, "_call_gemini", return_value=MOCK_BRIEFING):
        result = await agent.run(
            fivetran_reports=[MOCK_FIVETRAN_REPORT],
            bq_reports=[MOCK_BQ_REPORT],
            contradiction_report={"is_stale": False},
        )

    assert result["connections_ok"] == 1
    assert result["anomalies"] == []


@pytest.mark.asyncio
async def test_briefing_agent_includes_anomaly_when_stale():
    from agent.specialists.briefing_agent import BriefingAgent

    stale_briefing = {
        **MOCK_BRIEFING,
        "summary": "Silent staleness detected on arrivals table.",
        "anomalies": [{"connection": "conn_abc123", "lag_display": "4h 41m"}],
    }
    agent = BriefingAgent()
    with patch.object(agent, "_call_gemini", return_value=stale_briefing):
        result = await agent.run(
            fivetran_reports=[MOCK_FIVETRAN_REPORT],
            bq_reports=[MOCK_BQ_REPORT],
            contradiction_report={"is_stale": True, "lag_display": "4h 41m"},
        )

    assert len(result["anomalies"]) == 1
    assert result["anomalies"][0]["lag_display"] == "4h 41m"
