# Aftercall — Team Task Split (3 people)

12-hour hackathon, balanced full-stack team of 3. Goal of the day: **one real
call → webhook → DB → a dot turns green on a live map.** Build the spine
end-to-end first; everything past the green dot is polish.

## Rules every role must honor (competition + ethics)

- **Opt-in only** — never call anyone not flagged `opted_in`.
- **Iron rule** — the agent triages and connects, never treats/diagnoses; every
  🔴 DISTRESS case reaches a human (emergency contact called + operator alerted).
- **Dial is the spine, not a single API call** — judging axis 2 is won by depth
  across the 5 primitives (outbound triage, escalation calls, in/outbound SMS,
  inbound voice, webhooks).
- **"Who pays" must be live on stage** — axis 1 (Stripe, deferred — see below).
- **Phone-native** — axis 3 = something impossible on a screen (money over SMS in
  the first hour).
- **Keys in `.env` only, never committed; Stripe stays `sk_test_...`.** Store
  one-line transcript summaries only (privacy).

## Hour-0 joint task (do together before splitting)

Freeze the API contract + DB schema and stub the three endpoints so all three can
work in parallel against stubs.

- `POST /events` body `{playbook, polygon}` → `{event_id}`
- `GET /events/{event_id}/status` → counters + dots `[{person_id, name, lat, lng, status}]`
- `POST /webhooks/dial` ← Dial events
- Status protocol: agent ends every call with `STATUS=<OK|NEEDS_HELP|DISTRESS> | SUMMARY=<one line>`

---

## Main Task 1 — Telephony / Dial spine  (owns judging axis 2)

**Files:** `backend/dispatcher.py`, Dial half of `backend/app.py`, `backend/.env.example`

- [ ] Hour-0: Dial number + API key; confirm one live outbound call connects.
- [ ] Find the real Dial **rate limit** → set `MAX_CONCURRENT_CALLS`.
- [ ] Stand up ngrok → set `PUBLIC_BASE_URL` for webhooks.
- [ ] `place_call()` — real Dial integration (place-a-voice-call).
- [ ] Parallel fan-out with `asyncio.Semaphore(MAX_CONCURRENT_CALLS)`.
- [ ] `build_system_prompt()` — per-person Hebrew prompt; drill the exact
      `STATUS=… | SUMMARY=…` line until reliable.
- [ ] **Verify webhook field names early** (`type`/`answered`/`transcript`/
      `metadata.person_id` are guesses — silently breaks triage if wrong).
- [ ] Cover all 5 Dial primitives: escalation call to emergency contact,
      outbound + inbound SMS, inbound voice callback.

## Main Task 2 — Backend / Data + state machine

**Files:** `backend/models.py`, events API in `backend/app.py`, `backend/triage.py`

- [ ] `models.py`: `init_db`, seed ~30 demo people, **point-in-polygon** query,
      save/aggregate results.
- [ ] `POST /events` + `GET /events/{id}/status` (counters + dots) — frozen contract.
- [ ] `triage.classify_call()`: regex the STATUS line; unparsable-but-answered →
      conservative `NEEDS_HELP` + human-review flag; no answer → `UNREACHED`.
- [ ] `handle_status` machine: DISTRESS → trigger escalation call + operator alert.
- [ ] UNREACHED retry (max 2, 10-min delay) → SMS fallback.

DB schema (SQLite):
```
people(id, name, phone, lang, lat, lng, age, medical_notes, emergency_contact_phone, opted_in)
events(id, playbook_id, polygon, started_at, status)
call_results(id, event_id, person_id, status, attempt, transcript_summary, updated_at)
```

## Main Task 3 — Frontend / Demo  (owns judging axes 1 & 3 on stage)

**Files:** `dashboard/index.html`, `playbooks/*.yaml`, demo script

- [ ] Leaflet map: polygon draw, 🟢🟡🔴⚫ dots, counters, poll
      `GET /events/{id}/status` every 2s. **Demo lives or dies here.**
- [ ] `playbooks/rocket_alert.yaml` (demo scenario, Hebrew).
- [ ] `playbooks/earthquake.yaml` (proves crisis-agnosticism — "Tokyo, zero code").
- [ ] Own the ~3-min demo script + narration, planted distress / NEEDS_HELP
      volunteers, two rehearsals.
- [ ] Pre-stage everything: polygon coords, seeded numbers, test data.
- [ ] Stage phones on silent-but-vibrate so 30 ringing phones don't drown the pitch.

---

## Integration milestone (the goal of the day — shared)

ONE real call → webhook → DB → green dot on the map. Task 1 + Task 2 pair on
this; nothing else matters until it is solid.

## Deferred — Stripe (floating, after the green dot)

Owned by whoever finishes their spine work first. Do NOT touch until the
green-dot milestone works. Test mode only (`sk_test_...`).

1. **Layer A — who pays (axis 1):** one metered usage record per person reached +
   a visible invoice/Checkout.
2. **Layer B — phone-native (axis 3):** one end-to-end micro-grant: NEEDS_HELP →
   Dial SMS Payment Link → reply YES → test-mode disbursement → shown on the map.
3. **Layer C — donation surge:** optional closer; cut first if time is short.
