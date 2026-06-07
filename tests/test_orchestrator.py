import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from conftest import MOCK_FIVETRAN_REPORT, MOCK_BQ_REPORT

MOCK_CONTRADICTION = {
    "is_stale": True,
    "lag_display": "4h 41m",
    "lag_seconds": 16_740,
    "sla_breach_eta": {"breach_eta_minutes": 135, "confidence": "high", "trend": "worsening"},
    "recommendation": "Trigger incremental resync after human approval",
}

MOCK_BRIEFING = {
    "summary": "Silent staleness detected.",
    "connections_ok": 0,
    "anomalies": [{"connection": "conn_abc123", "lag_display": "4h 41m"}],
    "actions_taken": [],
}


@pytest.mark.asyncio
async def test_orchestrator_full_run_stale():
    from agent.orchestrator import Orchestrator

    orch = Orchestrator()
    with patch("agent.specialists.sync_sentinel.SyncSentinel.run", new_callable=AsyncMock, return_value=[MOCK_FIVETRAN_REPORT]), \
         patch("agent.specialists.data_doctor.DataDoctor.run", new_callable=AsyncMock, return_value=[MOCK_BQ_REPORT]), \
         patch("agent.critic.Critic.check", return_value={"is_safe": True, "flagged_fields": [], "challenges": []}), \
         patch("agent.specialists.impact_mapper.ImpactMapper.run", new_callable=AsyncMock, return_value=MOCK_CONTRADICTION), \
         patch("agent.specialists.briefing_agent.BriefingAgent.run", new_callable=AsyncMock, return_value=MOCK_BRIEFING):

        result = await orch.run()

    assert result["needs_recovery"] is True
    assert result["contradiction"]["is_stale"] is True
    assert result["briefing"]["connections_ok"] == 0


@pytest.mark.asyncio
async def test_orchestrator_aborts_on_injection():
    from agent.orchestrator import Orchestrator, InjectionDetected

    orch = Orchestrator()
    with patch("agent.specialists.sync_sentinel.SyncSentinel.run", new_callable=AsyncMock, return_value=[MOCK_FIVETRAN_REPORT]), \
         patch("agent.specialists.data_doctor.DataDoctor.run", new_callable=AsyncMock, return_value=[MOCK_BQ_REPORT]), \
         patch("agent.critic.Critic.check", return_value={"is_safe": False, "flagged_fields": ["schema"], "challenges": []}):

        with pytest.raises(InjectionDetected):
            await orch.run()


@pytest.mark.asyncio
async def test_orchestrator_healthy_no_recovery():
    from agent.orchestrator import Orchestrator

    healthy_contradiction = {
        "is_stale": False,
        "lag_display": "2m",
        "lag_seconds": 120,
        "sla_breach_eta": None,
        "recommendation": "No action needed",
    }
    healthy_briefing = {
        "summary": "All connections healthy.",
        "connections_ok": 1,
        "anomalies": [],
        "actions_taken": [],
    }
    orch = Orchestrator()
    with patch("agent.specialists.sync_sentinel.SyncSentinel.run", new_callable=AsyncMock, return_value=[MOCK_FIVETRAN_REPORT]), \
         patch("agent.specialists.data_doctor.DataDoctor.run", new_callable=AsyncMock, return_value=[MOCK_BQ_REPORT]), \
         patch("agent.critic.Critic.check", return_value={"is_safe": True, "flagged_fields": [], "challenges": []}), \
         patch("agent.specialists.impact_mapper.ImpactMapper.run", new_callable=AsyncMock, return_value=healthy_contradiction), \
         patch("agent.specialists.briefing_agent.BriefingAgent.run", new_callable=AsyncMock, return_value=healthy_briefing):

        result = await orch.run()

    assert result["needs_recovery"] is False
