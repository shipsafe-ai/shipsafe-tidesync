from typing import Any

from google.cloud import bigquery

import config

_client: bigquery.Client | None = None


def _get_client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=config.GCP_PROJECT)
    return _client


async def query_freshness(table: str, timestamp_col: str = "_fivetran_synced") -> dict[str, Any]:
    client = _get_client()
    full_table = f"`{config.GCP_PROJECT}.{config.BQ_DATASET}.{table}`"

    freshness_sql = f"""
        SELECT
            MAX({timestamp_col}) AS last_synced,
            COUNT(*) AS row_count,
            TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX({timestamp_col}), SECOND) AS lag_seconds
        FROM {full_table}
    """
    freshness_job = client.query(freshness_sql)
    rows = list(freshness_job.result())
    row = rows[0] if rows else {}

    # Null-rate per column
    schema = client.get_table(f"{config.GCP_PROJECT}.{config.BQ_DATASET}.{table}").schema
    null_rates: dict[str, float] = {}
    for field in schema:
        if field.name.startswith("_fivetran"):
            continue
        null_sql = f"""
            SELECT SAFE_DIVIDE(COUNTIF({field.name} IS NULL), COUNT(*)) AS null_rate
            FROM {full_table}
        """
        null_job = client.query(null_sql)
        null_rows = list(null_job.result())
        null_rates[field.name] = float(null_rows[0]["null_rate"] or 0.0) if null_rows else 0.0

    max_synced = row.get("last_synced")
    return {
        "table": table,
        "max_synced_at": max_synced.isoformat() if max_synced else None,
        "row_count": int(row.get("row_count") or 0),
        "lag_seconds": int(row.get("lag_seconds") or 0),
        "null_rates": null_rates,
    }


async def list_tables() -> list[str]:
    client = _get_client()
    tables = client.list_tables(f"{config.GCP_PROJECT}.{config.BQ_DATASET}")
    return [t.table_id for t in tables]
