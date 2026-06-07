import json
from typing import Any

import vertexai
from vertexai.generative_models import GenerativeModel

import config

_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "connections_ok": {"type": "integer"},
        "anomaly_count": {"type": "integer"},
        "anomalies_text": {"type": "string"},
        "actions_taken": {"type": "array", "items": {"type": "string"}},
        "overall_health": {"type": "string"},
    },
    "required": ["summary", "connections_ok", "anomaly_count", "anomalies_text", "actions_taken", "overall_health"],
}


class BriefingAgent:
    """Synthesizes a morning briefing from all pipeline signals using Gemini."""

    def _get_model(self) -> GenerativeModel:
        vertexai.init(project=config.GCP_PROJECT, location="us-central1")
        return GenerativeModel(config.GEMINI_MODEL)

    async def run(
        self,
        fivetran_reports: list[dict[str, Any]],
        bq_reports: list[dict[str, Any]],
        contradiction_report: dict[str, Any],
    ) -> dict[str, Any]:
        structured_context = {
            "fivetran_reports": fivetran_reports,
            "bq_reports": bq_reports,
            "contradiction": contradiction_report,
        }
        return await self._call_gemini(structured_context)

    async def _call_gemini(self, context: dict[str, Any]) -> dict[str, Any]:
        model = self._get_model()
        prompt = (
            "You are a data reliability engineer. "
            "Generate a concise morning briefing for the data team based on the following "
            "pipeline health report. Be direct and actionable.\n\n"
            f"PIPELINE REPORT:\n{json.dumps(context, indent=2)}\n"
        )
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        return json.loads(response.text)
