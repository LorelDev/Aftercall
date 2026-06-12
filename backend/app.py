"""Aftercall — FastAPI: events API + Dial webhook receiver.

Frozen contract (docs/REQUIREMENTS.md §5):
  POST /events                 {playbook, polygon} -> {event_id}
  GET  /events/{id}/status     -> counters + per-person dots
  POST /webhooks/dial          <- Dial events (call.ended, message.received, ...)

Hackathon scope: no auth/signup. Secrets in .env. Stripe test mode only.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any, Optional

# Load .env BEFORE importing modules that read env at import time (dial_client etc.)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import dispatcher
import models
import stripe_relief
import triage
from playbooks_loader import PlaybookError, list_playbooks, load_playbook

app = FastAPI(title="Aftercall", version="1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

DIAL_WEBHOOK_SECRET = os.environ.get("DIAL_WEBHOOK_SECRET", "")
# Dedupe on X-Dial-Event-ID (at-least-once delivery).
_SEEN_EVENT_IDS: set[str] = set()


@app.on_event("startup")
def _startup() -> None:
    models.init_db()
    # Seed once if empty (idempotent demo convenience).
    conn = models.connect()
    n = conn.execute("SELECT COUNT(*) AS c FROM people").fetchone()["c"]
    conn.close()
    if n == 0:
        models.seed_demo_people()


# ---------------------------------------------------------------------------
# Contract: POST /events
# ---------------------------------------------------------------------------
class EventIn(BaseModel):
    playbook: str
    polygon: list[list[float]]


@app.post("/events")
async def create_event(body: EventIn) -> dict[str, Any]:
    try:
        load_playbook(body.playbook)  # validate up front
    except PlaybookError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if len(body.polygon) < 3:
        raise HTTPException(status_code=400, detail="polygon needs >= 3 points")

    event_id = models.create_event(body.playbook, body.polygon)
    # Fan out parallel triage calls (await so failures surface; calls themselves
    # are non-blocking on Dial's side — they return 'initiated' immediately).
    summary = await dispatcher.dispatch_event(event_id, body.playbook, body.polygon)
    return {"event_id": event_id, **summary}


# ---------------------------------------------------------------------------
# Ad-hoc campaign: enter phones in the dashboard -> call them all at once
# ---------------------------------------------------------------------------
class CampaignPerson(BaseModel):
    name: str = ""
    phone: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    emergency_contact_phone: Optional[str] = None


class CampaignIn(BaseModel):
    playbook: str = "wellbeing_check"
    people: list[CampaignPerson]


# Default scatter center if a person has no coordinates (Tel Aviv).
_DEFAULT_CENTER = (32.0700, 34.7800)


@app.post("/campaigns")
async def create_campaign(body: CampaignIn) -> dict[str, Any]:
    try:
        load_playbook(body.playbook)
    except PlaybookError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not body.people:
        raise HTTPException(status_code=400, detail="no people provided")

    event_id = models.create_event(body.playbook, [])  # no polygon for ad-hoc
    created = []
    import random
    for i, cp in enumerate(body.people):
        lat = cp.lat if cp.lat is not None else _DEFAULT_CENTER[0] + random.uniform(-0.006, 0.006)
        lng = cp.lng if cp.lng is not None else _DEFAULT_CENTER[1] + random.uniform(-0.006, 0.006)
        name = cp.name.strip() or f"משתתף/ת {i + 1}"
        pid = models.add_person(name, cp.phone, lat, lng,
                                emergency_contact_phone=cp.emergency_contact_phone)
        created.append({"person_id": pid, "name": name, "lat": lat, "lng": lng})

    people_rows = [models.get_person(c["person_id"]) for c in created]
    summary = await dispatcher.dispatch_people(event_id, body.playbook, people_rows)
    return {"event_id": event_id, "people": created, **summary}


# ---------------------------------------------------------------------------
# Contract: GET /events/{id}/status
# ---------------------------------------------------------------------------
@app.get("/events/{event_id}/status")
def event_status(event_id: int) -> dict[str, Any]:
    status = models.event_status(event_id)
    reached = sum(
        status["counters"].get(s, 0) for s in ("OK", "NEEDS_HELP", "DISTRESS")
    )
    status["invoice"] = stripe_relief.usage_invoice(reached)
    status["relief_pool"] = stripe_relief.pool_status()
    status["alerts"] = [a for a in triage.OPERATOR_ALERTS if a["event_id"] == event_id]
    return status


# ---------------------------------------------------------------------------
# Contract: POST /webhooks/dial
# ---------------------------------------------------------------------------
@app.post("/webhooks/dial")
async def dial_webhook(
    request: Request,
    x_dial_event_type: Optional[str] = Header(default=None),
    x_dial_event_id: Optional[str] = Header(default=None),
    x_dial_signature: Optional[str] = Header(default=None),
) -> JSONResponse:
    raw = await request.body()

    # Verify HMAC signature if a secret is configured (skip in local dev).
    if DIAL_WEBHOOK_SECRET:
        expected = hmac.new(DIAL_WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        if not x_dial_signature or not hmac.compare_digest(expected, x_dial_signature):
            raise HTTPException(status_code=401, detail="bad signature")

    # Dedupe.
    if x_dial_event_id:
        if x_dial_event_id in _SEEN_EVENT_IDS:
            return JSONResponse({"ok": True, "deduped": True})
        _SEEN_EVENT_IDS.add(x_dial_event_id)

    payload = await _json(request, raw)
    etype = (payload.get("type") or x_dial_event_type or "").lower()
    data = payload.get("data", {})

    if etype == "call.ended":
        result = await triage.classify_call(
            call_id=data.get("callId"),
            ended_status=data.get("status", ""),
            canceled=bool(data.get("canceled", False)),
        )
        return JSONResponse({"ok": True, "handled": "call.ended", "result": result})

    if etype == "call.transcript.ready":
        # Same handler — fetch + classify (idempotent via upsert).
        result = await triage.classify_call(
            call_id=data.get("callId"), ended_status="completed", canceled=False,
        )
        return JSONResponse({"ok": True, "handled": "call.transcript.ready", "result": result})

    if etype == "message.received":
        result = await triage.handle_inbound_sms(
            from_phone=data.get("from", ""), body=data.get("body", ""),
        )
        return JSONResponse({"ok": True, "handled": "message.received", "result": result})

    if etype == "webhook.ping":
        return JSONResponse({"ok": True, "handled": "ping"})

    return JSONResponse({"ok": True, "ignored": etype})


# ---------------------------------------------------------------------------
# Convenience endpoints (not part of the frozen contract)
# ---------------------------------------------------------------------------
@app.get("/playbooks")
def playbooks() -> dict[str, Any]:
    return {"playbooks": list_playbooks()}


@app.get("/health")
def health() -> dict[str, Any]:
    import dial_client
    import supabase_store
    return {
        "ok": True,
        "dial_dry_run": dial_client.DRY_RUN,
        "stripe_dry_run": stripe_relief.DRY_RUN,
        "supabase": supabase_store.ENABLED,
        "max_concurrent_calls": dispatcher.MAX_CONCURRENT_CALLS,
    }


async def _json(request: Request, raw: bytes) -> dict[str, Any]:
    import json
    try:
        return json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON")
