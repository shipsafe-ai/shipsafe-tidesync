import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_recovery_agent_requires_approval():
    """RecoveryAgent must never trigger sync without an approved token."""
    from agent.specialists.recovery_agent import RecoveryAgent, ApprovalRequired

    agent = RecoveryAgent()
    with pytest.raises(ApprovalRequired):
        await agent.execute(connection_id="conn_abc123", approval_token=None)


@pytest.mark.asyncio
async def test_recovery_agent_runs_setup_tests_first():
    from agent.specialists.recovery_agent import RecoveryAgent
    import config as cfg

    agent = RecoveryAgent()
    with patch("agent.tools.fivetran_mcp.run_connection_setup_tests", new_callable=AsyncMock) as mock_test, \
         patch("agent.tools.fivetran_mcp.sync_connection", new_callable=AsyncMock) as mock_sync, \
         patch.object(agent, "_validate_token", return_value=True), \
         patch.object(cfg, "FIVETRAN_ALLOW_WRITES", True):

        mock_test.return_value = {"status": "passed", "tests": [{"name": "auth", "status": "passed"}]}
        mock_sync.return_value = {"id": "sync_001", "status": "syncing"}

        result = await agent.execute(connection_id="conn_abc123", approval_token="valid_token_xyz")

    mock_test.assert_awaited_once_with("conn_abc123")
    mock_sync.assert_awaited_once_with("conn_abc123")
    assert result["tests_passed"] is True
    assert result["sync_triggered"] is True


@pytest.mark.asyncio
async def test_recovery_agent_aborts_if_tests_fail():
    from agent.specialists.recovery_agent import RecoveryAgent
    import config as cfg

    agent = RecoveryAgent()
    with patch("agent.tools.fivetran_mcp.run_connection_setup_tests", new_callable=AsyncMock) as mock_test, \
         patch("agent.tools.fivetran_mcp.sync_connection", new_callable=AsyncMock) as mock_sync, \
         patch.object(agent, "_validate_token", return_value=True), \
         patch.object(cfg, "FIVETRAN_ALLOW_WRITES", True):

        mock_test.return_value = {"status": "failed", "tests": [{"name": "auth", "status": "failed"}]}

        result = await agent.execute(connection_id="conn_abc123", approval_token="valid_token_xyz")

    mock_sync.assert_not_awaited()
    assert result["tests_passed"] is False
    assert result["sync_triggered"] is False


@pytest.mark.asyncio
async def test_recovery_agent_blocked_when_writes_disabled(monkeypatch):
    import config
    monkeypatch.setattr(config, "FIVETRAN_ALLOW_WRITES", False)

    from agent.specialists.recovery_agent import RecoveryAgent, WritesDisabled

    agent = RecoveryAgent()
    with patch.object(agent, "_validate_token", return_value=True):
        with pytest.raises(WritesDisabled):
            await agent.execute(connection_id="conn_abc123", approval_token="valid_token_xyz")
