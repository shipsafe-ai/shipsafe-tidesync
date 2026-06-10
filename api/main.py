import asyncio
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
from agent.ais_stream import get_ais_contradiction_context, get_vessel_snapshot, start_ais_feed
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
            pass
    # Start AIS feed in background if API key configured
    ais_key = config.get_secret("AISSTREAM_API_KEY") if hasattr(config, "get_secret") else ""
    if not ais_key:
        import os
        ais_key = os.environ.get("AISSTREAM_API_KEY", "")
    if ais_key:
        asyncio.create_task(start_ais_feed(ais_key))
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

    ft_reports = result.pop("_fivetran_reports", [])
    bq_reports_raw = result.pop("_bq_reports", [])
    contradiction = result.get("contradiction", {})

    # BriefingAgent runs in background — doesn't block /run response
    async def _briefing_task() -> None:
        global _latest_briefing
        try:
            b = await orchestrator.briefing_agent.run(
                fivetran_reports=ft_reports,
                bq_reports=bq_reports_raw,
                contradiction_report=contradiction,
            )
            _latest_briefing = b
        except Exception:
            pass

    asyncio.create_task(_briefing_task())

    critic_challenge = result.get("critic_challenge", {})

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
            "critic_challenge": critic_challenge,
            "briefing": {},
        }

    return {
        "status": "complete",
        "briefing": {},
        "contradiction": result["contradiction"],
        "critic_challenge": critic_challenge,
    }


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
    try:
        return await sync_sentinel.run()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "connections": []})


@app.get("/mcp/tools")
async def mcp_tools():
    """List the tools exposed by the official Fivetran MCP server (live verification).

    Proves the real MCP integration: TideSync spawns fivetran/fivetran-mcp over stdio
    and the control-plane reads (SyncSentinel) flow through it, with REST as fallback.
    """
    from agent.tools import fivetran_mcp_client
    try:
        names = await fivetran_mcp_client.list_tool_names()
        return {
            "server": "fivetran/fivetran-mcp",
            "transport": "stdio",
            "connected": True,
            "tool_count": len(names),
            "tools": names,
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "server": "fivetran/fivetran-mcp",
                "connected": False,
                "error": str(e),
                "note": "Control-plane reads fall back to direct Fivetran REST.",
            },
        )


@app.get("/freshness")
async def freshness(connection_id: str | None = None):
    try:
        if connection_id:
            return await data_doctor.run(connection_id=connection_id)
        reports = await sync_sentinel.run()
        all_bq = []
        for r in reports:
            # Skip internal Fivetran bookkeeping connectors and paused ones
            if r.get("service") == "fivetran_log" or r.get("paused"):
                continue
            try:
                bq = await data_doctor.run(connection_id=r["connection_id"])
                all_bq.extend(bq)
            except Exception:
                pass
        return all_bq
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "reports": []})


@app.get("/briefing")
async def briefing():
    return _latest_briefing or {"summary": "No briefing yet. POST /run to generate."}


@app.post("/webhooks/fivetran")
async def fivetran_webhook(
    request: Request,
    x_fivetran_signature: str | None = Header(default=None),
):
    body = await request.body()

    # Fivetran sends a signature-less ping during webhook registration to verify the URL.
    # Accept unsigned pings as liveness checks; enforce HMAC on real events.
    if x_fivetran_signature is None:
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {}
        return {"received": True, "event": payload.get("event", "ping")}

    # Verify HMAC-SHA256 signature on signed events
    try:
        secret = _get_webhook_secret()
    except Exception:
        secret = ""

    if secret:
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, x_fivetran_signature):
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


@app.get("/ais")
async def ais_status():
    """Live AIS vessel positions in the Hormuz corridor — used for contradiction detection."""
    return {
        "vessels": get_ais_contradiction_context(),
        "source": "aisstream.io",
        "bounding_box": "24-28N 54-60E (Hormuz corridor)",
    }


@app.get("/ais/{mmsi}")
async def ais_vessel(mmsi: str):
    """AIS snapshot for a specific vessel MMSI."""
    snap = get_vessel_snapshot(mmsi)
    if not snap:
        return JSONResponse({"error": "vessel not tracked or no AIS data yet"}, status_code=404)
    return snap


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
