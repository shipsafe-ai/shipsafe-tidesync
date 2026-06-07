import hashlib
import hmac
import json
import secrets as py_secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
from agent.orchestrator import Orchestrator
from agent.specialists.data_doctor import DataDoctor
from agent.specialists.recovery_agent import ApprovalRequired, RecoveryAgent, WritesDisabled
from agent.specialists.sync_sentinel import SyncSentinel
from agent.tools import fivetran_mcp

orchestrator = Orchestrator()
sync_sentinel = SyncSentinel()
data_doctor = DataDoctor()

_pending_approvals: dict[str, dict[str, Any]] = {}
_latest_briefing: dict[str, Any] = {}
_sse_subscribers: list = []


def _get_webhook_secret() -> str:
    return config.get_secret("WEBHOOK_SECRET")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if config.TIDESYNC_PUBLIC_URL:
        try:
            webhooks = await fivetran_mcp.list_webhooks()
            tidesync_url = f"{config.TIDESYNC_PUBLIC_URL}/webhooks/fivetran"
            if not any(w.get("url") == tidesync_url for w in webhooks):
                await fivetran_mcp.create_account_webhook(
                    url=tidesync_url,
                    events=["sync_end", "connection_failure"],
                    secret=_get_webhook_secret(),
                )
        except Exception:
            pass  # non-fatal: webhook registration fails gracefully
    yield


app = FastAPI(title="TideSync", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/run")
async def run():
    result = await orchestrator.run()

    if result["needs_recovery"]:
        token = py_secrets.token_hex(16)
        _pending_approvals[token] = {
            "connection_id": result["connection_id"],
            "action": "sync",
            "contradiction": result["contradiction"],
        }
        return {
            "status": "awaiting_approval",
            "approval_token": token,
            "contradiction": result["contradiction"],
            "briefing": result["briefing"],
        }

    global _latest_briefing
    _latest_briefing = result.get("briefing", {})
    return {"status": "complete", "briefing": result["briefing"], "contradiction": result["contradiction"]}


class _TokenRecovery(RecoveryAgent):
    """RecoveryAgent that validates against the pending_approvals store."""

    def __init__(self, token: str) -> None:
        self._token = token

    def _validate_token(self, token: str) -> bool:
        return token == self._token and token in _pending_approvals


@app.post("/approve/{token}")
async def approve(token: str):
    req = _pending_approvals.pop(token, None)
    if req is None:
        raise HTTPException(status_code=404, detail="Token expired or invalid")

    agent = _TokenRecovery(token=token)
    # Re-insert temporarily so _validate_token passes
    _pending_approvals[token] = req
    try:
        result = await agent.execute(
            connection_id=req["connection_id"],
            approval_token=token,
        )
    except WritesDisabled as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ApprovalRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    finally:
        _pending_approvals.pop(token, None)

    return result


@app.get("/connections")
async def connections():
    return await sync_sentinel.run()


@app.get("/freshness")
async def freshness(connection_id: str | None = None):
    if connection_id:
        return await data_doctor.run(connection_id=connection_id)
    # Return all connections' freshness
    reports = await sync_sentinel.run()
    all_bq = []
    for r in reports:
        bq = await data_doctor.run(connection_id=r["connection_id"])
        all_bq.extend(bq)
    return all_bq


@app.get("/briefing")
async def briefing():
    return _latest_briefing or {"summary": "No briefing yet. POST /run to generate."}


@app.post("/webhooks/fivetran")
async def fivetran_webhook(
    request: Request,
    x_fivetran_signature: str | None = Header(default=None),
):
    body = await request.body()

    # Verify HMAC-SHA256 signature
    try:
        secret = _get_webhook_secret()
    except Exception:
        secret = ""

    if secret:
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, x_fivetran_signature or ""):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = json.loads(body)
    event = payload.get("event")
    connection_id = payload.get("connector_id")

    if event == "sync_end" and connection_id:
        bq_reports = await data_doctor.run(connection_id=connection_id)
        for report in bq_reports:
            if report.get("lag_seconds", 0) > config.STALE_THRESHOLD_SECONDS:
                # Broadcast staleness alert via SSE
                alert = {
                    "type": "staleness_alert",
                    "connection_id": connection_id,
                    "lag_seconds": report["lag_seconds"],
                    "lag_display": _format_lag(report["lag_seconds"]),
                    "table": report["table"],
                }
                for queue in _sse_subscribers:
                    await queue.put(alert)
                break

    return {"received": True, "event": event}


def _format_lag(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


# Mount Next.js static export if present
_static_dir = Path(__file__).parent.parent / "dashboard" / "out"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="dashboard")
