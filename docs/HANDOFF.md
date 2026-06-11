# HANDOFF PROMPT — paste this into any AI coding assistant

You are joining **Aftercall**, a 12-hour hackathon project (Dial "My Agent Has a
Phone" hackathon, Tel Aviv, June 2026, team of 3). Read this fully before writing
any code.

## What Aftercall is

**One-liner:** "The first hour after any crisis, at infinite scale."

After any disaster (earthquake, hurricane, rocket alert, wildfire, building power
outage), no authority can quickly answer: **who is OK and who is not?** Today
it's done with volunteers and spreadsheets. Aftercall launches thousands of
*parallel outbound AI voice calls* to an opted-in population inside a geographic
polygon, triages every answer, escalates real distress to humans, and renders a
live ops map for the authority.

**Iron rule (ethical + pitch core):** the agent NEVER treats anyone. It triages
and connects. Every red case reaches a human (emergency contact called + human
operator alerted). Crisis-agnostic engine; everything crisis-specific lives in
YAML playbooks.

## Stack & platform

- **Telephony:** Dial (https://docs.getdial.ai) — gives the agent a phone
  number; outbound AI voice calls driven by a system prompt we provide; SMS
  send/receive; webhooks/event stream. Python SDK or REST.
- **Backend:** Python 3.12, FastAPI, SQLite (hackathon-grade, no auth, API key in
  `.env`).
- **Dashboard:** single-file HTML + Leaflet, polls `GET /events/{id}/status`
  every 2s.
- **Demo audience numbers:** ~30 "demo residents" = team + hackathon volunteers'
  real phones.

## Architecture (implemented as skeletons)

```
Trigger (POST /events {playbook, polygon})
  → dispatcher.py: load playbook YAML → get_people_in_polygon → build per-person
    Hebrew system prompt → parallel Dial calls (asyncio, Semaphore(MAX_CONCURRENT))
  → Dial webhook POST /webhooks/dial:
      call.ended → triage.classify_call → save_call_result → handle_status
      sms.received → "1"=OK, "2"=NEEDS_HELP
  → triage statuses: OK 🟢 | NEEDS_HELP 🟡 | DISTRESS 🔴 | UNREACHED ⚫
      DISTRESS → call emergency contact (via Dial) + operator alert
      UNREACHED → retry after 10 min (max 2 attempts) → SMS fallback
  → dashboard polls aggregate status → colored dots on map + counters
```

**Status protocol:** the voice agent is prompted to end every call by saying a
machine-readable line: `STATUS=<OK|NEEDS_HELP|DISTRESS> | SUMMARY=<one line>`.
`triage.classify_call()` regex-parses it from the transcript; unparsable →
conservative `NEEDS_HELP` + human review flag.

**DB schema (SQLite):**
```
people(id, name, phone, lang, lat, lng, age, medical_notes, emergency_contact_phone, opted_in)
events(id, playbook_id, polygon, started_at, status)
call_results(id, event_id, person_id, status, attempt, transcript_summary, updated_at)
```

**Internal API contract (frozen — do not change):**
- `POST /events` body `{playbook, polygon}` → `{event_id}`
- `GET /events/{event_id}/status` → counters + per-person dots
  `[{person_id, name, lat, lng, status}]`
- `POST /webhooks/dial` ← Dial events

## Priority order (what to build next)

1. **Real Dial integration in `dispatcher.place_call()`** — exact SDK/REST shape
   from https://docs.getdial.ai/documentation/capabilities/place-a-voice-call.
   Verify webhook payload field names in `app.py`/`triage.py` against
   https://docs.getdial.ai/documentation/platform/webhooks (current field names
   are guesses: `type`, `answered`, `transcript`, `metadata.person_id`).
2. **`models.py` implementation** (init_db, seed 30 demo people, queries).
3. **Dashboard map** — the demo lives or dies on this screen.
4. Escalation call to emergency contact; retry; SMS fallback.
5. Integration milestone: ONE real call → webhook → DB → dot turns green on map.
   Everything else is polish.

## Conventions & constraints

- Hour-0 check: real Dial rate limits → set `MAX_CONCURRENT_CALLS` accordingly.
- Voice prompts are in Hebrew, calm, short, no drama; prompt template is in
  `dispatcher.build_system_prompt()` — iterate on real people early.
- No auth/signup, no production hardening — 12-hour hackathon.
- Keep transcripts as one-line summaries (privacy).
- Demo script and known pitfalls are in `docs/TASKS.md` — read before changing
  flow.
- Pitch framing: opt-in only, human-in-the-loop escalation is a FEATURE; global
  angle = same engine, different playbook (Tokyo earthquake = new YAML, zero
  code).
