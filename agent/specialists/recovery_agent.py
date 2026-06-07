from typing import Any

from agent.tools import fivetran_mcp
import config


class ApprovalRequired(Exception):
    pass


class WritesDisabled(Exception):
    pass


class RecoveryAgent:
    """Triggers Fivetran resync — ONLY after human approval. Never auto-executes."""

    def _validate_token(self, token: str) -> bool:
        # Token validation delegated to FastAPI approval gate.
        # Subclasses / tests override this.
        raise NotImplementedError("Token validation must be handled by the API layer")

    async def execute(
        self,
        connection_id: str,
        approval_token: str | None,
    ) -> dict[str, Any]:
        if not approval_token:
            raise ApprovalRequired("Human approval token required before triggering any sync.")

        if not self._validate_token(approval_token):
            raise ApprovalRequired("Invalid or expired approval token.")

        if not config.FIVETRAN_ALLOW_WRITES:
            raise WritesDisabled(
                "FIVETRAN_ALLOW_WRITES is false. Enable writes and obtain human approval first."
            )

        test_result = await fivetran_mcp.run_connection_setup_tests(connection_id)
        tests_passed = test_result.get("status") == "passed"

        if not tests_passed:
            return {
                "tests_passed": False,
                "sync_triggered": False,
                "test_result": test_result,
            }

        sync_result = await fivetran_mcp.sync_connection(connection_id)
        return {
            "tests_passed": True,
            "sync_triggered": True,
            "sync_id": sync_result.get("id"),
            "sync_status": sync_result.get("status"),
        }
