"""Triage: classify calls, run the status state machine, escalate distress to a
human, retry the unreached, and fall back to SMS.

Status protocol (frozen, exact ASCII):
    STATUS=<OK|NEEDS_HELP|DISTRESS> | SUMMARY=<one line>

Iron rule: the agent triages and connects, never treats. Every DISTRESS routes
to a human (emergency contact called + operator alert). Red is never auto-closed.
"""
from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Optional

import dial_client
import models
import supabase_store
from playbooks_loader import load_playbook

# No-answer flow: SMS immediately, wait, then call again (operator decision).
RETRY_DELAY_SECONDS = int(os.environ.get("RETRY_DELAY_SECONDS", str(2 * 60)))
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "2"))

# Exact machine-readable line. Tolerant of whitespace/case around the keywords.
# LOCATION is optional ("-" or absent when the person gave no address).
_STATUS_RE = re.compile(
    r"STATUS\s*=\s*(OK|NEEDS_HELP|DISTRESS)\s*\|\s*SUMMARY\s*=\s*([^|\r\n]+)"
    r"(?:\|\s*LOCATION\s*=\s*([^|\r\n]+))?",
    re.IGNORECASE,
)

# In-memory operator alert feed (hackathon scope; dashboard polls it).
OPERATOR_ALERTS: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def parse_status_line(transcript: str) -> Optional[tuple[str, str, Optional[str]]]:
    """Return (status, summary, location) if the machine-readable line is present."""
    if not transcript:
        return None
    last = None
    for m in _STATUS_RE.finditer(transcript):
        last = m  # take the LAST occurrence (the agent's closing line)
    if not last:
        return None
    status = last.group(1).upper()
    summary = last.group(2).strip().splitlines()[0][:280]
    loc_raw = (last.group(3) or "").strip()
    location = loc_raw.splitlines()[0][:200] if loc_raw else None
    if location in ("-", "—", "אין", "none", "N/A", "n/a"):
        location = None
    return status, summary, location


async def classify_call(call_id: str, ended_status: str, canceled: bool) -> dict[str, Any]:
    """Two-step (docs/DIAL.md): the webhook has no inline transcript.

    1. If the call did not complete -> UNREACHED.
    2. Else fetch transcript via GET /calls/{id}, regex the STATUS line.
    3. Answered-but-unparsable -> conservative NEEDS_HELP + human-review flag.
    """
    correlation = models.lookup_call(call_id)
    if not correlation:
        return {"error": "unknown call_id", "call_id": call_id}
    person_id = correlation["person_id"]
    event_id = correlation["event_id"]
    kind = correlation.get("kind", "triage")

    # Escalation calls don't change the resident's triage status.
    if kind == "escalation":
        return {"call_id": call_id, "kind": "escalation", "noted": True}

    existing = models.get_result(event_id, person_id)
    attempt = existing["attempt"] if existing else 1

    person = models.get_person(person_id) or {}

    if canceled or ended_status != "completed":
        await _set_status(event_id, person_id, "UNREACHED", attempt,
                          summary=f"call {ended_status}")
        supabase_store.log_bg(
            channel="voice", call_id=call_id, event_id=event_id,
            person_id=person_id, person_name=person.get("name", ""),
            phone=person.get("phone", ""), status="UNREACHED",
            summary=f"call {ended_status}",
        )
        return {"call_id": call_id, "person_id": person_id, "status": "UNREACHED"}

    try:
        call = await dial_client.fetch_call(call_id)
        transcript = call.get("transcript", "")
    except dial_client.DialError as e:
        transcript = ""

    parsed = parse_status_line(transcript)
    if parsed:
        status, summary, location = parsed
    else:
        # Answered but unparsable: never silently mark OK.
        status, summary, location = "NEEDS_HELP", "ענה אך ללא שורת STATUS — לבדיקת אדם", None

    if location:
        await update_location(person_id, location)

    await _set_status(event_id, person_id, status, attempt, summary=summary,
                      transcript=transcript, needs_review=(parsed is None))
    supabase_store.log_bg(
        channel="voice", call_id=call_id, event_id=event_id,
        person_id=person_id, person_name=person.get("name", ""),
        phone=person.get("phone", ""), status=status, summary=summary,
        transcript=transcript,
    )
    return {"call_id": call_id, "person_id": person_id, "status": status, "summary": summary}


# ---------------------------------------------------------------------------
# Location: the person told the agent where they are -> move their map dot
# ---------------------------------------------------------------------------
async def update_location(person_id: int, address: str) -> None:
    """Geocode a spoken address (Nominatim, IL-biased) and update the person."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0)) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": address, "format": "json", "limit": 1,
                        "countrycodes": "il", "accept-language": "he"},
                headers={"User-Agent": "beseder-emergency-checkin/1.0"},
            )
        results = resp.json()
        if results:
            models.update_person_location(
                person_id, float(results[0]["lat"]), float(results[0]["lon"]))
    except Exception:
        pass  # best-effort: a failed geocode must never break triage


# ---------------------------------------------------------------------------
# Status state machine
# ---------------------------------------------------------------------------
async def _set_status(event_id: int, person_id: int, status: str, attempt: int,
                      summary: str = "", transcript: str = "",
                      needs_review: bool = False) -> None:
    models.upsert_result(event_id, person_id, status, attempt=attempt,
                         summary=summary, transcript=transcript)
    await handle_status(event_id, person_id, status, attempt, needs_review)


async def handle_status(event_id: int, person_id: int, status: str,
                        attempt: int, needs_review: bool = False) -> None:
    event = models.get_event(event_id)
    playbook = load_playbook(event["playbook_id"]) if event else {}

    if status == "DISTRESS":
        await escalate_distress(event_id, person_id, playbook)
    elif status == "UNREACHED":
        await handle_unreached(event_id, person_id, playbook, attempt)
    elif status == "NEEDS_HELP":
        if needs_review:
            _alert_operator(event_id, person_id, "NEEDS_HELP (לבדיקת אדם)")


async def escalate_distress(event_id: int, person_id: int, playbook: dict[str, Any]) -> None:
    """Human-in-the-loop: call the emergency contact AND alert an operator."""
    person = models.get_person(person_id)
    if not person:
        return
    # 1) operator alert (always, even if the contact call fails)
    _alert_operator(event_id, person_id, "DISTRESS 🔴 — נדרש גורם אנושי")
    # 2) automatic outbound call to the emergency contact
    import dispatcher  # local import avoids a cycle
    try:
        await dispatcher.place_escalation_call(person, playbook, event_id)
    except dial_client.DialError as e:
        _alert_operator(event_id, person_id, f"כשל בחיוג לאיש קשר: {e}")


async def handle_unreached(event_id: int, person_id: int, playbook: dict[str, Any],
                           attempt: int) -> None:
    """No answer -> SMS immediately, wait RETRY_DELAY (2 min), call again.

    The SMS goes out on the FIRST miss so the person can reply 1/2 right away;
    later misses don't re-send it (they already have it on their phone).
    """
    if attempt == 1:
        await sms_fallback(event_id, person_id, playbook)
    if attempt < MAX_ATTEMPTS:
        asyncio.create_task(_retry_after_delay(event_id, person_id, attempt + 1))


async def _retry_after_delay(event_id: int, person_id: int, next_attempt: int) -> None:
    await asyncio.sleep(RETRY_DELAY_SECONDS)
    # Re-place a single triage call for this person.
    event = models.get_event(event_id)
    if not event:
        return
    playbook = load_playbook(event["playbook_id"])
    person = models.get_person(person_id)
    if not person:
        return
    import dispatcher
    prompt = dispatcher.build_system_prompt(person, playbook)
    try:
        resp = await dial_client.place_call(
            to=person["phone"], outbound_instruction=prompt,
            language=person.get("lang", "he-IL"),
        )
        if resp.get("id"):
            models.map_call(resp["id"], person_id, event_id, kind="triage")
        models.upsert_result(event_id, person_id, "PENDING", attempt=next_attempt)
    except dial_client.DialError:
        models.upsert_result(event_id, person_id, "UNREACHED", attempt=next_attempt,
                             summary="retry place_call failed")


async def sms_fallback(event_id: int, person_id: int, playbook: dict[str, Any]) -> None:
    person = models.get_person(person_id)
    if not person:
        return
    body = playbook.get("sms", {}).get(
        "fallback_body", "Aftercall: השב/י 1 אם את/ה בסדר, או 2 אם נדרשת עזרה."
    )
    try:
        await dial_client.send_sms(to=person["phone"], body=body)
        supabase_store.log_bg(
            channel="sms", direction="outbound", event_id=event_id,
            person_id=person_id, person_name=person.get("name", ""),
            phone=person["phone"], transcript=body,
            summary="SMS fallback אחרי אי-מענה",
        )
    except dial_client.DialError:
        pass


# ---------------------------------------------------------------------------
# Inbound SMS -> status
# ---------------------------------------------------------------------------
async def handle_inbound_sms(from_phone: str, body: str) -> dict[str, Any]:
    """message.received drives status: '1'=OK, '2'=NEEDS_HELP."""
    person = models.get_person_by_phone(from_phone)
    if not person:
        return {"error": "unknown sender", "from": from_phone}
    text = (body or "").strip().upper()
    event_id = _latest_event_id()

    # Every inbound SMS is part of the record, recognized or not.
    supabase_store.log_bg(
        channel="sms", direction="inbound", event_id=event_id,
        person_id=person["id"], person_name=person.get("name", ""),
        phone=from_phone, transcript=body or "",
    )

    if text.startswith("1"):
        status, summary = "OK", "אישר/ה בטוח/ה ב-SMS"
    elif text.startswith("2"):
        status, summary = "NEEDS_HELP", "ביקש/ה עזרה ב-SMS"
    else:
        return {"person_id": person["id"], "intent": "unrecognized", "body": body}

    if event_id is not None:
        await _set_status(event_id, person["id"], status, attempt=MAX_ATTEMPTS,
                          summary=summary, transcript=f"SMS מהאדם: {body}")
        # ack
        ack_key = "ok_ack" if status == "OK" else "needs_help_ack"
        event = models.get_event(event_id)
        playbook = load_playbook(event["playbook_id"]) if event else {}
        ack = playbook.get("sms", {}).get(ack_key)
        if ack:
            try:
                await dial_client.send_sms(to=from_phone, body=ack)
                supabase_store.log_bg(
                    channel="sms", direction="outbound", event_id=event_id,
                    person_id=person["id"], person_name=person.get("name", ""),
                    phone=from_phone, transcript=ack, summary="SMS אישור קבלה",
                )
            except dial_client.DialError:
                pass
    return {"person_id": person["id"], "intent": "status", "status": status}


def _latest_event_id() -> Optional[int]:
    conn = models.connect()
    row = conn.execute("SELECT id FROM events ORDER BY started_at DESC LIMIT 1").fetchone()
    conn.close()
    return row["id"] if row else None


def _alert_operator(event_id: int, person_id: int, message: str) -> None:
    person = models.get_person(person_id)
    OPERATOR_ALERTS.append({
        "event_id": event_id,
        "person_id": person_id,
        "name": person["name"] if person else "",
        "message": message,
        "ts": __import__("time").time(),
    })
