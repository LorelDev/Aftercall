"""Thin async client for the Dial REST API (the spine).

Verified surface (docs/DIAL.md):
  Base:   https://getdial.ai/api/v1
  Auth:   Authorization: Bearer sk_live_...
  Calls:  POST /calls    {to, fromNumberId, outboundInstruction, language}
  SMS:    POST /messages {to, fromNumberId, body}
  Fetch:  GET  /calls/{id}   -> transcript (shape VERIFY LIVE)

Notes:
  - Endpoints are NOT idempotent: a retry places a *second* call / sends a *second*
    SMS. Callers confirm failure before retrying.
  - The webhook carries no metadata; correlation is handled in models.call_map.
  - If DIAL_API_KEY is unset we run in DRY_RUN: no network, deterministic fake ids.
    This lets the whole system be built/tested before a real key exists.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Optional

import httpx

DIAL_BASE_URL = os.environ.get("DIAL_BASE_URL", "https://getdial.ai/api/v1")
DIAL_API_KEY = os.environ.get("DIAL_API_KEY", "")
DIAL_FROM_NUMBER_ID = os.environ.get("DIAL_FROM_NUMBER_ID", "")
DRY_RUN = not bool(DIAL_API_KEY)

_TIMEOUT = httpx.Timeout(20.0, connect=10.0)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {DIAL_API_KEY}",
        "Content-Type": "application/json",
    }


class DialError(RuntimeError):
    pass


async def place_call(to: str, outbound_instruction: str,
                     language: str = "he-IL",
                     from_number_id: Optional[str] = None) -> dict[str, Any]:
    """POST /calls. Returns {id, status}. Caller must persist id -> person."""
    from_id = from_number_id or DIAL_FROM_NUMBER_ID
    if DRY_RUN:
        return {"id": f"call_dry_{uuid.uuid4().hex[:16]}", "status": "initiated", "_dry_run": True}
    payload = {
        "to": to,
        "fromNumberId": from_id,
        "outboundInstruction": outbound_instruction,
        "language": language,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{DIAL_BASE_URL}/calls", json=payload, headers=_headers())
    if resp.status_code >= 300:
        raise DialError(f"place_call {resp.status_code}: {resp.text}")
    return _unwrap(resp.json(), "call")


async def send_sms(to: str, body: str,
                   from_number_id: Optional[str] = None) -> dict[str, Any]:
    """POST /messages. Returns {id, status}."""
    from_id = from_number_id or DIAL_FROM_NUMBER_ID
    if DRY_RUN:
        return {"id": f"msg_dry_{uuid.uuid4().hex[:16]}", "status": "queued", "_dry_run": True}
    payload = {"to": to, "fromNumberId": from_id, "body": body}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{DIAL_BASE_URL}/messages", json=payload, headers=_headers())
    if resp.status_code >= 300:
        raise DialError(f"send_sms {resp.status_code}: {resp.text}")
    return _unwrap(resp.json(), "message")


async def fetch_call(call_id: str) -> dict[str, Any]:
    """GET /calls/{id}. The webhook has no inline transcript; fetch it here.

    Transcript shape is VERIFY-LIVE — we normalize a few likely shapes into a
    single 'transcript' string so triage has one thing to parse.
    """
    if DRY_RUN:
        return {"id": call_id, "status": "completed", "transcript": ""}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{DIAL_BASE_URL}/calls/{call_id}", headers=_headers())
    if resp.status_code >= 300:
        raise DialError(f"fetch_call {resp.status_code}: {resp.text}")
    data = _unwrap(resp.json(), "call")
    data["transcript"] = _normalize_transcript(data)
    return data


def _unwrap(body: dict[str, Any], key: str) -> dict[str, Any]:
    """The live API wraps resources, e.g. {"ok":true,"call":{...}}. Return the
    inner object if present, else the body itself (tolerant of both shapes)."""
    inner = body.get(key)
    if isinstance(inner, dict):
        return inner
    return body


def _normalize_transcript(data: dict[str, Any]) -> str:
    """Coalesce possible transcript shapes into one string (VERIFY LIVE)."""
    t = data.get("transcript")
    if isinstance(t, str):
        return t
    if isinstance(t, list):  # list of turns
        parts = []
        for turn in t:
            if isinstance(turn, dict):
                parts.append(str(turn.get("text") or turn.get("content") or ""))
            else:
                parts.append(str(turn))
        return "\n".join(parts)
    if isinstance(t, dict):
        return str(t.get("text") or t.get("content") or "")
    # alternate keys some APIs use
    for k in ("transcriptText", "text", "summary"):
        if isinstance(data.get(k), str):
            return data[k]
    return ""
