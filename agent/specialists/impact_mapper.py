import json
from typing import Any

import vertexai
from vertexai.generative_models import GenerativeModel

import config

_SCHEMA = {
    "type": "object",
    "properties": {
        "is_stale": {"type": "boolean"},
        "lag_display": {"type": "string"},
        "lag_seconds": {"type": "integer"},
        "sla_breach_eta_minutes": {"type": "integer"},
        "breach_confidence": {"type": "string"},
        "lag_trend": {"type": "string"},
        "cost_rec": {"type": "string"},
        "recommendation": {"type": "string"},
    },
    "required": ["is_stale", "lag_display", "lag_seconds", "recommendation", "cost_rec", "lag_trend"],
}

_STALE_THRESHOLD = config.STALE_THRESHOLD_SECONDS


class ImpactMapper:
    """Uses Gemini to reason across Fivetran + BigQuery sources and detect contradictions."""

    def _get_model(self) -> GenerativeModel:
        vertexai.init(project=config.GCP_PROJECT, location="us-central1")
        return GenerativeModel(config.GEMINI_MODEL)

    async def run(
        self,
        fivetran_report: dict[str, Any],
        bq_report: dict[str, Any],
    ) -> dict[str, Any]:
        structured_input = {
            "fivetran": {
                "connection_id": fivetran_report.get("connection_id"),
                "status": fivetran_report.get("status"),
                "succeeded_at": fivetran_report.get("succeeded_at"),
                "sync_frequency_minutes": fivetran_report.get("sync_frequency"),
                "row_count": fivetran_report.get("row_count"),
            },
            "bigquery": {
                "table": bq_report.get("table"),
                "max_synced_at": bq_report.get("max_synced_at"),
                "row_count": bq_report.get("row_count"),
                "lag_seconds": bq_report.get("lag_seconds"),
                "null_rates": bq_report.get("null_rates", {}),
            },
            "stale_threshold_seconds": _STALE_THRESHOLD,
        }
        return await self._call_gemini(structured_input)

    async def _call_gemini(self, structured_input: dict[str, Any]) -> dict[str, Any]:
        model = self._get_model()
        schema_str = json.dumps(_SCHEMA, indent=2)
        prompt = (
            "You are a data pipeline reliability analyst. "
            "Analyze the following structured pipeline report and detect contradictions "
            "between what Fivetran reports (control plane) and what BigQuery shows (data truth). "
            f"Return ONLY a JSON object matching this schema:\n{schema_str}\n\n"
            f"INPUT:\n{json.dumps(structured_input, indent=2)}\n\n"
            "Populate all required fields. Use lag_seconds from bigquery.lag_seconds. "
            "sla_breach_eta_minutes: -1 if not stale, 0 if already breached, else minutes remaining. "
            "lag_trend: based on whether lag is growing vs sync frequency."
        )
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        return json.loads(response.text)
