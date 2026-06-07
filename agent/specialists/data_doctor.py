from typing import Any

from agent.tools import bigquery_client, fivetran_mcp


class DataDoctor:
    """Queries BigQuery directly for data-truth freshness metrics."""

    async def run(self, connection_id: str) -> list[dict[str, Any]]:
        schema_config = await fivetran_mcp.get_connection_schema_config(connection_id)
        tables = self._extract_enabled_tables(schema_config)

        if not tables:
            tables = await bigquery_client.list_tables()

        reports = []
        for table in tables:
            report = await bigquery_client.query_freshness(table)
            reports.append(report)

        return reports

    def _extract_enabled_tables(self, schema_config: dict) -> list[str]:
        tables = []
        schemas = schema_config.get("schemas", {})
        for schema_name, schema_data in schemas.items():
            for table_name, table_data in schema_data.get("tables", {}).items():
                if table_data.get("enabled", True):
                    tables.append(table_name)
        return tables
