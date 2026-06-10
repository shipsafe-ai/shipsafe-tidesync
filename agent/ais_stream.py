"""
AIS stream integration for TideSync.

Connects to aisstream.io, subscribes to PositionReport in the Hormuz/Jebel Ali
corridor, extracts ETA data, and surfaces it for contradiction detection:

  AIS says:      "Ever Given ETA Jebel Ali: 2026-06-09T06:00Z"
  BigQuery says: "last arrival record: 2026-06-07T14:33Z, lag=39h"
  Gemini:        "silent staleness — vessel en route but data frozen"
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"

# Hormuz + Jebel Ali approach corridor
BOUNDING_BOX = {
    "MinLatitude": 24.0,
    "MaxLatitude": 28.0,
    "MinLongitude": 54.0,
    "MaxLongitude": 60.0,
}

# Tracked MMSIs — our fixture vessels in the Hormuz scenario
TRACKED_MMSI = {
    "353136000",  # Ever Given
    "255806178",  # MSC Gülsün
    "440350900",  # HMM Algeciras
    "220625000",  # Maersk Mc-Kinney Møller
    "477310400",  # COSCO Shipping Universe
}

# In-memory cache: mmsi → latest AIS position snapshot
_vessel_cache: dict[str, dict[str, Any]] = {}


def get_vessel_snapshot(mmsi: str | None = None) -> dict[str, Any] | list[dict[str, Any]]:
    """Return cached AIS position for a vessel or all vessels."""
    if mmsi:
        return _vessel_cache.get(mmsi, {})
    return list(_vessel_cache.values())


def get_ais_contradiction_context() -> list[dict[str, Any]]:
    """
    Return AIS position data formatted for ImpactMapper contradiction detection.
    Each entry has: mmsi, name, lat, lon, speed, eta_destination, last_seen_utc
    """
    return [
        {
            "mmsi": v["mmsi"],
            "name": v.get("name", v["mmsi"]),
            "lat": v["lat"],
            "lon": v["lon"],
            "speed_kn": v["speed"],
            "heading": v["heading"],
            "destination": v.get("destination", "JEBEL ALI"),
            "nav_status": v.get("nav_status", 0),
            "last_seen_utc": v["last_seen_utc"],
            "ais_source": "aisstream.io",
        }
        for v in _vessel_cache.values()
    ]


async def _connect(api_key: str) -> None:
    try:
        import websockets  # type: ignore

        async with websockets.connect(AISSTREAM_URL) as ws:
            await ws.send(json.dumps({
                "APIKey": api_key,
                "BoundingBoxes": [[BOUNDING_BOX]],
                "FiltersShipMMSI": list(TRACKED_MMSI),
                "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
            }))
            log.info("AISstream connected — tracking %d vessels in Hormuz corridor", len(TRACKED_MMSI))

            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    mtype = msg.get("MessageType", "")
                    meta = msg.get("Metadata", {})
                    body = msg.get("Message", {}).get(mtype, {})
                    mmsi = str(meta.get("MMSI") or body.get("UserID") or "")
                    if not mmsi:
                        continue

                    if mtype == "PositionReport":
                        _vessel_cache[mmsi] = {
                            "mmsi": mmsi,
                            "name": (meta.get("ShipName") or "").strip() or mmsi,
                            "lat": body.get("Latitude", meta.get("latitude", 0)),
                            "lon": body.get("Longitude", meta.get("longitude", 0)),
                            "speed": body.get("Sog", 0),
                            "heading": body.get("TrueHeading") or body.get("Cog") or 0,
                            "nav_status": body.get("NavigationalStatus", 0),
                            "last_seen_utc": datetime.now(timezone.utc).isoformat(),
                        }
                    elif mtype == "ShipStaticData":
                        existing = _vessel_cache.get(mmsi, {"mmsi": mmsi})
                        existing["name"] = (body.get("Name") or "").strip() or existing.get("name", mmsi)
                        existing["destination"] = (body.get("Destination") or "").strip()
                        existing["draught"] = body.get("MaximumStaticDraught")
                        existing["imo"] = body.get("ImoNumber")
                        _vessel_cache[mmsi] = existing

                except Exception:
                    continue

    except Exception as e:
        log.warning("AISstream disconnected: %s — retrying in 10s", e)
        await asyncio.sleep(10)


async def start_ais_feed(api_key: str) -> None:
    """Run AIS feed in background — reconnects automatically."""
    while True:
        await _connect(api_key)
        await asyncio.sleep(10)
