# Aftercall — Team Task Split (3 people, fully parallel)

12-hour hackathon, balanced full-stack team of 3. Each main task below is a
**self-contained vertical**: it runs, is testable, and is demoable on its own —
**no task waits on another task or on a previous step.** The only shared thing is
the frozen contract (below), which is just a written agreement, not code anyone
has to finish first.

## The seam that makes everything parallel

Everyone codes against the **frozen contract + fixtures**, not against each
other's running code:

- `POST /events` body `{playbook, polygon}` → `{event_id}`
- `GET /events/{event_id}/status` → counters + dots `[{person_id, name, lat, lng, status}]`
- `POST /webhooks/dial` ← Dial events
- Status protocol: agent ends every call with `STATUS=<OK|NEEDS_HELP|DISTRESS> | SUMMARY=<one line>`

Commit a `fixtures/` folder up front (5 min, anyone): a sample `status.json`
response, a sample Dial `call.ended` webhook body, and ~30 seed people as JSON.
Each person builds against these fixtures, so all three verticals are green
before anything is wired together. Integration is then just deleting mocks.

## Rules every role must honor (competition + ethics)

- **Opt-in only** — never call anyone not flagged `opted_in`.
- **Iron rule** — the agent triages and connects, never treats/diagnoses; every
  🔴 DISTRESS case reaches a human (emergency contact called + operator alerted).
- **Dial is the spine, not a single API call** — judging axis 2 wants depth
  across the 5 primitives (outbound triage, escalation calls, in/outbound SMS,
  inbound voice, webhooks).
- **Phone-native** — axis 3 = something impossible on a screen.
- **Keys in `.env` only, never committed; Stripe stays `sk_test_...`.** Store
  one-line transcript summaries only (privacy).

---

## Main Task 1 — Dial telephony (runs against a fake DB, no waiting)

Owns judging axis 2. **Independent because:** it talks to the Dial sandbox and a
local stub, never to Task 2's real database.

**Files:** `backend/dispatcher.py`, `backend/dial_client.py`, `backend/.env.example`

- [ ] Hour-0: Dial number + API key; confirm one live outbound call connects.
- [ ] Find the real Dial **rate limit** → set `MAX_CONCURRENT_CALLS`; ngrok →
      `PUBLIC_BASE_URL`.
- [ ] `place_call()` — real Dial integration (place-a-voice-call).
- [ ] Parallel fan-out with `asyncio.Semaphore(MAX_CONCURRENT_CALLS)`.
- [ ] `build_system_prompt()` — per-person Hebrew prompt; drill the exact
      `STATUS=… | SUMMARY=…` line until reliable.
- [ ] Verify webhook field names and **write the real `call.ended` body into
      `fixtures/webhook_call_ended.json`** — this unblocks Task 2 without coupling.
- [ ] Escalation call, outbound + inbound SMS, inbound voice callback.
- **Test in isolation:** feed `dispatcher` a `people.json` fixture list and place
  calls to the team's own phones; log results to stdout (no DB needed).

## Main Task 2 — Backend / Data + triage (runs without any phone, no waiting)

**Independent because:** triage and the API are pure functions over fixtures; no
real call ever has to happen to build or test this.

**Files:** `backend/models.py`, `backend/app.py`, `backend/triage.py`

- [ ] `models.py`: `init_db`, seed ~30 demo people from `fixtures/people.json`,
      **point-in-polygon** query, save/aggregate results.
- [ ] `POST /events` + `GET /events/{id}/status` — serve the frozen contract.
- [ ] `triage.classify_call()`: regex the STATUS line; unparsable-but-answered →
      conservative `NEEDS_HELP` + review flag; no answer → `UNREACHED`.
- [ ] `handle_status` machine: DISTRESS → call a `notify()` hook (Task 1 swaps in
      the real escalation call later); UNREACHED → retry (max 2, 10-min) → SMS hook.
- **Test in isolation:** `POST /webhooks/dial` with
  `fixtures/webhook_call_ended.json` via curl → assert the dot flips and counters
  move. No Dial, no frontend.

DB schema (SQLite):
```
people(id, name, phone, lang, lat, lng, age, medical_notes, emergency_contact_phone, opted_in)
events(id, playbook_id, polygon, started_at, status)
call_results(id, event_id, person_id, status, attempt, transcript_summary, updated_at)
```

## Main Task 3 — Frontend / Demo (runs against a static JSON, no waiting)

Owns judging axes 1 & 3 on stage. **Independent because:** the dashboard polls a
URL — point it at `fixtures/status.json` (or `python -m http.server`) and build
the whole map before the backend exists.

**Files:** `dashboard/index.html`, `playbooks/*.yaml`, `docs/DEMO.md`

- [ ] Leaflet map: polygon draw, 🟢🟡🔴⚫ dots, counters, poll every 2s.
      **Demo lives or dies here.** Build against `fixtures/status.json`, then flip
      the base URL to `localhost:8000` at the end — one-line change.
- [ ] `playbooks/rocket_alert.yaml` (demo, Hebrew) + `playbooks/earthquake.yaml`
      (crisis-agnostic — "Tokyo, zero code").
- [ ] `docs/DEMO.md`: ~3-min script + narration, planted distress / NEEDS_HELP
      volunteers, two rehearsals.
- [ ] Pre-stage everything: polygon coords, seeded numbers, test data; phones on
      silent-but-vibrate.

---

## Wire-up (happens last, ~30 min, not a blocker for anyone)

Because all three built against the same fixtures, integration is mechanical:
Task 3 flips its base URL to the live API, Task 2 swaps its `notify()`/SMS hooks
for Task 1's real Dial calls, and a real `call.ended` webhook replaces the
fixture. Target: ONE real call → webhook → DB → green dot on the map.

## Deferred — Stripe (floating, after the green dot)

Owned by whoever finishes their vertical first. Test mode only (`sk_test_...`).

1. **Layer A — who pays (axis 1):** one metered usage record + a visible invoice.
2. **Layer B — phone-native (axis 3):** NEEDS_HELP → Dial SMS Payment Link →
   reply YES → test-mode disbursement → shown on the map.
3. **Layer C — donation surge:** optional closer; cut first if time is short.
