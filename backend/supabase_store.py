"""Supabase persistence for full interaction transcripts (voice calls + SMS).

Every interaction is one row in `call_transcripts`: a finished voice call (full
transcript + parsed status/summary) or a single SMS (inbound or outbound).
That guarantees a record exists even when the whole exchange happened over SMS.

Graceful no-op when SUPABASE_URL / SUPABASE_KEY are unset, so the system runs
without Supabase configured. Writes are fire-and-forget (log_bg) — a Supabase
outage must never block or fail triage.

Run once in the Supabase SQL editor:

    create table if not exists public.call_transcripts (
      id          bigint generated always as identity primary key,
      call_id     text,
      event_id    bigint,
      person_id   bigint,
      person_name text,
      phone       text,
      channel     text not null default 'voice',  -- voice | sms
      direction   text,                           -- sms only: inbound | outbound
      status      text,                           -- OK | NEEDS_HELP | DISTRESS | UNREACHED
      summary     text,
      transcript  text,
      created_at  timestamptz not null default now()
    );
    alter table public.call_transcripts enable row level security;
    -- The backend uses the publishable (anon) key, so inserts need a policy.
    -- Reads stay blocked: transcripts are write-only from the public key's view.
    create policy "backend inserts" on public.call_transcripts
      for insert to anon with check (true);

Note: docs/TOS.md §2 calls for storing one-line summaries only; storing full
transcripts here is an explicit product decision by the operator.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
TABLE = os.environ.get("SUPABASE_TRANSCRIPTS_TABLE", "call_transcripts")
ENABLED = bool(SUPABASE_URL and SUPABASE_KEY)

_TIMEOUT = httpx.Timeout(15.0, connect=8.0)


async def log_interaction(*, channel: str, call_id: Optional[str] = None,
                          event_id: Optional[int] = None,
                          person_id: Optional[int] = None,
                          person_name: str = "", phone: str = "",
                          direction: Optional[str] = None,
                          status: str = "", summary: str = "",
                          transcript: str = "") -> bool:
    """Insert one interaction row. Returns False (silently) when disabled/failed."""
    if not ENABLED:
        return False
    row = {
        "call_id": call_id,
        "event_id": event_id,
        "person_id": person_id,
        "person_name": person_name,
        "phone": phone,
        "channel": channel,
        "direction": direction,
        "status": status,
        "summary": summary,
        "transcript": transcript,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/{TABLE}",
                json=row,
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
            )
        return resp.status_code < 300
    except httpx.HTTPError:
        return False


def log_bg(**kwargs: Any) -> None:
    """Fire-and-forget wrapper; never raises into the caller's flow."""
    if not ENABLED:
        return
    try:
        asyncio.get_running_loop().create_task(log_interaction(**kwargs))
    except RuntimeError:
        pass  # no running loop (sync/test context) — skip rather than block
