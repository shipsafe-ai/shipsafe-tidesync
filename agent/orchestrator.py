from typing import Any

from agent.critic import Critic
from agent.specialists.briefing_agent import BriefingAgent
from agent.specialists.data_doctor import DataDoctor
from agent.specialists.impact_mapper import ImpactMapper
from agent.specialists.sync_sentinel import SyncSentinel


class InjectionDetected(Exception):
    pass


class Orchestrator:
    """ADK SequentialAgent: SyncSentinel → DataDoctor → Critic → ImpactMapper → BriefingAgent."""

    def __init__(self) -> None:
        self.sync_sentinel = SyncSentinel()
        self.data_doctor = DataDoctor()
        self.critic = Critic()
        self.impact_mapper = ImpactMapper()
        self.briefing_agent = BriefingAgent()

    async def run(self) -> dict[str, Any]:
        # 1. Fivetran control-plane truth
        fivetran_reports = await self.sync_sentinel.run()

        # 2. BigQuery data truth — skip paused or Fivetran system connectors
        all_bq_reports: list[dict[str, Any]] = []
        for report in fivetran_reports:
            if report.get("paused") or report.get("service") == "fivetran_log":
                continue
            bq_reports = await self.data_doctor.run(connection_id=report["connection_id"])
            all_bq_reports.extend(bq_reports)

        # Use first active (non-paused, non-system) connection for contradiction analysis
        active = [r for r in fivetran_reports if not r.get("paused") and r.get("service") != "fivetran_log"]
        ft_report = active[0] if active else (fivetran_reports[0] if fivetran_reports else {})
        bq_report = all_bq_reports[0] if all_bq_reports else {}

        # 3. Critic: prompt-injection check (ABORT if unsafe)
        verdict = self.critic.check(fivetran_report=ft_report, bq_report=bq_report)
        if not verdict["is_safe"]:
            raise InjectionDetected(
                f"Prompt injection detected in fields: {verdict['flagged_fields']}"
            )

        # 4. ImpactMapper: Gemini contradiction detection
        contradiction = await self.impact_mapper.run(
            fivetran_report=ft_report,
            bq_report=bq_report,
        )

        # 5. Critic Layer 2: Gemini adversarially challenges the staleness verdict
        critic_challenge = await self.critic.challenge_verdict(
            contradiction=contradiction,
            fivetran_report=ft_report,
            bq_report=bq_report,
        )

        # BriefingAgent runs in background (see api/main.py) — not awaited here
        return {
            "needs_recovery": contradiction.get("is_stale", False),
            "connection_id": ft_report.get("connection_id"),
            "contradiction": contradiction,
            "critic_verdict": verdict,
            "critic_challenge": critic_challenge,
            "_fivetran_reports": fivetran_reports,
            "_bq_reports": all_bq_reports,
        }
