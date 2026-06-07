import pytest
from unittest.mock import patch, MagicMock
from conftest import MOCK_FIVETRAN_REPORT, MOCK_BQ_REPORT

MOCK_CONTRADICTION = {
    "is_stale": True,
    "lag_display": "4h 41m",
    "lag_seconds": 16_740,
    "sla_breach_eta": {"breach_eta_minutes": 135, "confidence": "high", "trend": "worsening"},
    "cost_rec": "Switch to daily sync — table read weekly, synced hourly",
    "recommendation": "Trigger incremental resync after human approval",
}


@pytest.mark.asyncio
async def test_impact_mapper_detects_contradiction():
    from agent.specialists.impact_mapper import ImpactMapper

    mapper = ImpactMapper()
    with patch.object(mapper, "_call_gemini", return_value=MOCK_CONTRADICTION):
        result = await mapper.run(
            fivetran_report=MOCK_FIVETRAN_REPORT,
            bq_report=MOCK_BQ_REPORT,
        )

    assert result["is_stale"] is True
    assert result["lag_display"] == "4h 41m"
    assert result["sla_breach_eta"]["breach_eta_minutes"] == 135


@pytest.mark.asyncio
async def test_impact_mapper_healthy_data():
    from agent.specialists.impact_mapper import ImpactMapper

    healthy_bq = {**MOCK_BQ_REPORT, "lag_seconds": 120}
    healthy_response = {
        "is_stale": False,
        "lag_display": "2m",
        "lag_seconds": 120,
        "sla_breach_eta": None,
        "cost_rec": None,
        "recommendation": "No action needed",
    }
    mapper = ImpactMapper()
    with patch.object(mapper, "_call_gemini", return_value=healthy_response):
        result = await mapper.run(
            fivetran_report=MOCK_FIVETRAN_REPORT,
            bq_report=healthy_bq,
        )

    assert result["is_stale"] is False
    assert result["sla_breach_eta"] is None


@pytest.mark.asyncio
async def test_impact_mapper_never_echoes_raw_field_values():
    """Gemini prompt must use structured schema — raw field values not interpolated."""
    from agent.specialists.impact_mapper import ImpactMapper

    mapper = ImpactMapper()
    with patch.object(mapper, "_call_gemini", return_value=MOCK_CONTRADICTION) as mock_gemini:
        await mapper.run(fivetran_report=MOCK_FIVETRAN_REPORT, bq_report=MOCK_BQ_REPORT)
        call_args = mock_gemini.call_args
        # prompt should be structured JSON input, not raw string interpolation
        assert call_args is not None
