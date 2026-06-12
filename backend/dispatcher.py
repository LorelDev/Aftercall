"""Dispatcher: load playbook -> find targets -> build per-person Hebrew prompt ->
parallel Dial voice calls (concurrency-capped). Owns judging axis 2 depth.

Iron rule: we only ever place calls to opted-in people (models enforces the
opted_in filter); the agent triages and connects, never treats.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import dial_client
import models
from playbooks_loader import load_playbook

# Tuned to Dial's real rate limit — VERIFY LIVE in hour 0, then set here / in .env.
MAX_CONCURRENT_CALLS = int(os.environ.get("MAX_CONCURRENT_CALLS", "5"))

# Reconciliation poller: don't depend solely on the PubNub listen daemon (it can
# disconnect). After placing a call we also poll Dial directly until the call is
# terminal, then classify. The webhook path stays primary and is idempotent.
RECONCILE_INTERVAL = float(os.environ.get("RECONCILE_INTERVAL", "4"))
RECONCILE_TIMEOUT = float(os.environ.get("RECONCILE_TIMEOUT", "900"))  # 15 min
_TERMINAL_STATES = {"terminated", "completed", "failed", "no-answer", "busy", "canceled", "ended"}


def build_system_prompt(person: dict[str, Any], playbook: dict[str, Any]) -> str:
    """Per-person Hebrew system prompt. Drills the exact machine-readable
    STATUS line until reliable (the contract triage parses)."""
    voice = playbook.get("voice", {})
    base = voice.get("system_prompt", "")
    name = person.get("name", "")
    prompt = base.replace("{name}", name)

    # Per-person context appended so the agent personalizes without leaking PII
    # into logs (privacy: only summaries are ever stored).
    ctx_lines = [f"\n\n--- הקשר על האדם ---", f"שם: {name}"]
    if person.get("age"):
        ctx_lines.append(f"גיל: {person['age']}")
    if person.get("medical_notes"):
        ctx_lines.append(f"רקע רפואי ידוע (להתחשבות בלבד, לא לאבחון): {person['medical_notes']}")
    ctx_lines.append(
        "\nתזכורת אחרונה: אחרי הפרידה ולפני הניתוק, אמור שורה אחת בדיוק — "
        "STATUS=<OK|NEEDS_HELP|DISTRESS> | SUMMARY=<משפט אחד> | LOCATION=<כתובת או ->"
    )
    return prompt + "\n".join(ctx_lines)


async def _place_one(person: dict[str, Any], event_id: int, playbook: dict[str, Any],
                     sem: asyncio.Semaphore, attempt: int) -> dict[str, Any]:
    async with sem:
        prompt = build_system_prompt(person, playbook)
        lang = person.get("lang", playbook.get("language", "he-IL"))
        try:
            resp = await dial_client.place_call(
                to=person["phone"], outbound_instruction=prompt, language=lang
            )
        except dial_client.DialError as e:
            # Could not place: mark UNREACHED so the retry loop can pick it up.
            models.upsert_result(event_id, person["id"], "UNREACHED",
                                 attempt=attempt, summary=f"place_call failed: {e}")
            return {"person_id": person["id"], "error": str(e)}

        call_id = resp.get("id")
        if call_id:
            # CRITICAL: persist call_id -> person; the webhook has no metadata.
            models.map_call(call_id, person["id"], event_id, kind="triage")
            # Resilience: poll Dial directly in case the webhook never arrives.
            asyncio.create_task(reconcile_call(call_id))
        # PENDING until call.ended (webhook or reconciler) resolves it.
        models.upsert_result(event_id, person["id"], "PENDING", attempt=attempt)
        return {"person_id": person["id"], "call_id": call_id, "status": resp.get("status")}


async def reconcile_call(call_id: str) -> None:
    """Poll a call until terminal, then classify it (webhook-independent).

    Dial sometimes reports a finished call as In-Progress indefinitely, which
    used to leave the person PENDING forever. Two escapes: classify early once
    the transcript already carries the closing STATUS line, and resolve to
    UNREACHED when the timeout expires instead of giving up silently.
    """
    import triage  # local import avoids a cycle at module load
    deadline = asyncio.get_event_loop().time() + RECONCILE_TIMEOUT
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(RECONCILE_INTERVAL)
        if _already_resolved(call_id):
            return
        try:
            call = await dial_client.fetch_call(call_id)
        except dial_client.DialError:
            continue
        state = str(_call_state(call)).lower()
        if state not in _TERMINAL_STATES:
            # Stuck non-terminal but the conversation clearly ended.
            if triage.parse_status_line(call.get("transcript", "")):
                await triage.classify_call(call_id, ended_status="completed", canceled=False)
                return
            continue
        termination = (call.get("terminationType") or "").lower()
        answered = termination in ("completed", "") and state in ("terminated", "completed", "ended")
        ended_status = "completed" if answered else (termination or state)
        canceled = termination == "canceled" or state == "canceled"
        await triage.classify_call(call_id, ended_status=ended_status, canceled=canceled)
        return
    # Timed out without ever turning terminal: don't leave the dot hanging.
    if not _already_resolved(call_id):
        await triage.classify_call(call_id, ended_status="timeout", canceled=False)


def _already_resolved(call_id: str) -> bool:
    """True when the webhook (or an earlier poll) already settled this call."""
    corr = models.lookup_call(call_id)
    if not corr:
        return False
    existing = models.get_result(corr["event_id"], corr["person_id"])
    return bool(existing and existing["status"] != "PENDING")


def _call_state(call: dict[str, Any]) -> str:
    st = call.get("status")
    if isinstance(st, dict):
        return st.get("state", "")
    return st or ""


async def dispatch_event(event_id: int, playbook_id: str,
                         polygon: list[list[float]]) -> dict[str, Any]:
    """Fan out parallel triage calls to every opted-in person in the polygon."""
    playbook = load_playbook(playbook_id)
    targets = models.find_opted_in_in_polygon(polygon)
    models.add_targets(event_id, [p["id"] for p in targets])
    sem = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
    results = await asyncio.gather(
        *[_place_one(p, event_id, playbook, sem, attempt=1) for p in targets]
    )
    return {
        "event_id": event_id,
        "playbook_id": playbook_id,
        "targets": len(targets),
        "placed": [r for r in results if r.get("call_id")],
        "failed": [r for r in results if r.get("error")],
        "dry_run": dial_client.DRY_RUN,
    }


async def dispatch_people(event_id: int, playbook_id: str,
                          people: list[dict[str, Any]]) -> dict[str, Any]:
    """Ad-hoc campaign: fan out parallel calls to an explicit list of people
    (created on the fly from the dashboard), not a polygon query."""
    playbook = load_playbook(playbook_id)
    models.add_targets(event_id, [p["id"] for p in people])
    sem = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
    results = await asyncio.gather(
        *[_place_one(p, event_id, playbook, sem, attempt=1) for p in people]
    )
    return {
        "event_id": event_id,
        "playbook_id": playbook_id,
        "targets": len(people),
        "placed": [r for r in results if r.get("call_id")],
        "failed": [r for r in results if r.get("error")],
        "dry_run": dial_client.DRY_RUN,
    }


async def place_escalation_call(person: dict[str, Any], playbook: dict[str, Any],
                                event_id: int) -> dict[str, Any]:
    """DISTRESS -> outbound Dial voice call to the resident's emergency contact."""
    contact = person.get("emergency_contact_phone")
    if not contact:
        return {"error": "no emergency contact"}
    template = playbook.get("escalation", {}).get("contact_prompt", "")
    prompt = template.replace("{name}", person.get("name", ""))
    resp = await dial_client.place_call(
        to=contact, outbound_instruction=prompt,
        language=playbook.get("language", "he-IL"),
    )
    call_id = resp.get("id")
    if call_id:
        models.map_call(call_id, person["id"], event_id, kind="escalation")
    return {"person_id": person["id"], "contact": contact, "call_id": call_id}
