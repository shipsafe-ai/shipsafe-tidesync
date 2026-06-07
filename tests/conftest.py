import os
import pytest

os.environ.setdefault("GCP_PROJECT", "shipsafe-ai")
os.environ.setdefault("GEMINI_MODEL", "gemini-2.5-flash")
os.environ.setdefault("BQ_DATASET", "shipsafe_hormuz")
os.environ.setdefault("FIVETRAN_ALLOW_WRITES", "false")
os.environ.setdefault("STALE_THRESHOLD_SECONDS", "3600")


MOCK_CONNECTION = {
    "id": "conn_abc123",
    "schema": "hormuz_port_arrivals",
    "service": "google_sheets",
    "status": "connected",
    "succeeded_at": "2026-06-07T09:14:00Z",
    "failed_at": None,
    "sync_frequency": 60,
    "group_id": "grp_xyz",
    "paused": False,
    "sync_state": "scheduled",
}

MOCK_BQ_REPORT = {
    "table": "arrivals",
    "max_synced_at": "2026-06-07T06:45:00Z",
    "row_count": 1_200_000,
    "lag_seconds": 16_740,
    "null_rates": {"vessel_name": 0.0, "timestamp": 0.0, "port": 0.02},
}

MOCK_FIVETRAN_REPORT = {
    "connection_id": "conn_abc123",
    "status": "connected",
    "succeeded_at": "2026-06-07T09:14:00Z",
    "failed_at": None,
    "sync_frequency": 60,
    "row_count": 1_200_000,
    "destination_id": "dest_bq1",
    "group_id": "grp_xyz",
}
