# Aftercall — Build Plan

12-hour hackathon, team of 3. Goal of the day: **one real call → webhook → DB →
a dot turns green on a live map.** Everything past that is polish. Build the
spine end-to-end first; do not gold-plate any single piece.

**Judging-aware priorities** (see `docs/stack.md` for the full mapping):
- **Dial depth (criterion 2):** use Dial across multiple primitives — outbound
  triage calls, escalation calls, inbound + outbound SMS, inbound calls, event
  webhooks. The phone layer must be the spine, never a single API call.
- **Who pays (criterion 1):** Stripe makes the business model *live* — metered
  usage per person reached + a visible invoice/Checkout.
- **Phone-native (criterion 3):** Stripe emergency micro-grants delivered and
  confirmed **over SMS** — money moving at the speed of the phone.

## Roles

- **A — Telephony/Dial:** dispatcher + real Dial integration + webhook field
  verification.
- **B — Backend/Data:** models.py, events API, triage logic, escalation.
- **C — Frontend/Demo:** Leaflet dashboard, playbooks, demo script + narration.

Roles are a default, not a wall — whoever is unblocked grabs the next item.
**Stripe (Layers A/B)** is owned by whoever finishes their spine work first —
it's additive, not on the critical path to the green-dot milestone.

## Hour-0 checklist (do before writing features)

- [ ] Get a Dial number + API key; confirm an outbound test call connects.
- [ ] Find the real Dial **rate limit** → set `MAX_CONCURRENT_CALLS` accordingly.
- [ ] Stand up a public URL for webhooks (ngrok) → set `PUBLIC_BASE_URL`.
- [ ] Confirm the exact **place-a-call** request shape and **webhook** payload
      field names (`type` / `answered` / `transcript` / `metadata.person_id` are
      currently guesses).
- [ ] Collect ~30 real demo phone numbers (team + volunteers), opted in.
- [ ] Create a Stripe **test-mode** account; grab `sk_test_...`; note the test
      card `4242 4242 4242 4242` for the live demo disbursement/Checkout.

## Priority order (frozen)

1. **Real Dial integration in `dispatcher.place_call()`.**
   https://docs.getdial.ai/documentation/capabilities/place-a-voice-call —
   then verify webhook fields against
   https://docs.getdial.ai/documentation/platform/webhooks
2. **`models.py`** — init_db, seed ~30 demo people, point-in-polygon query,
   save/aggregate results.
3. **Dashboard map** — the demo lives or dies here.
4. **Escalation** — DISTRESS → call emergency contact + alert operator; retry
   UNREACHED (max 2, 10-min delay); SMS fallback.
5. **Integration milestone** — ONE real call flows all the way to a green dot.
6. **Stripe Layer A (who pays)** — record one metered usage unit per person
   reached; show a Checkout/invoice so the business model is real on stage.
7. **Stripe Layer B (phone-native)** — ONE end-to-end micro-grant: NEEDS_HELP →
   Dial SMS Payment Link → reply YES → test-mode disbursement → shown on map.
8. **Stripe Layer C (optional)** — live donation surge that converts to call
   capacity; closer only, cut first if time is short.

## Hour-by-hour (rough)

| Hours | Focus |
|------|-------|
| 0–1  | Hour-0 checklist; agree on the frozen API contract; skeleton runs. |
| 1–3  | A: real `place_call`. B: `models.py` done + seeded. C: map renders seeded dots. |
| 3–5  | First real call end-to-end; webhook → `classify_call` → DB → dot updates. |
| 5–7  | Parallel fan-out under the concurrency cap; counters live; tune polling. |
| 7–9  | Escalation path (DISTRESS contact call + operator alert); retry + SMS fallback. |
| 8–10 | Stripe Layer A (metered usage + invoice/Checkout) and Layer B (one SMS micro-grant, test mode). |
| 9–10 | Second playbook (earthquake) to prove crisis-agnosticism on stage. |
| 10–11| Iterate the Hebrew prompt on real people; calm/short/no-drama. |
| 11–12| Freeze. Rehearse the demo script twice. Pre-stage polygon + numbers + Stripe test data. |

## Architecture recap

```
POST /events {playbook, polygon}
  → dispatcher: load playbook YAML → get_people_in_polygon
    → build per-person Hebrew system prompt
    → parallel Dial calls (asyncio.Semaphore(MAX_CONCURRENT_CALLS))
  → POST /webhooks/dial:
      call.ended    → triage.classify_call → save_call_result → handle_status
      sms.received  → "1"=OK, "2"=NEEDS_HELP
  → statuses: OK 🟢 | NEEDS_HELP 🟡 | DISTRESS 🔴 | UNREACHED ⚫
      DISTRESS  → call emergency contact + operator alert
      UNREACHED → retry after 10 min (max 2) → SMS fallback
  → dashboard polls GET /events/{id}/status every 2s → colored dots + counters
```

### Frozen API contract — do not change

- `POST /events` body `{playbook, polygon}` → `{event_id}`
- `GET /events/{event_id}/status` → counters + dots `[{person_id, name, lat, lng, status}]`
- `POST /webhooks/dial` ← Dial events

### Status protocol

The voice agent ends every call with the exact line:

```
STATUS=<OK|NEEDS_HELP|DISTRESS> | SUMMARY=<one line>
```

`triage.classify_call()` regex-parses it. Unparsable but answered → conservative
`NEEDS_HELP` + human-review flag. Not answered → `UNREACHED`.

### DB schema (SQLite)

```
people(id, name, phone, lang, lat, lng, age, medical_notes, emergency_contact_phone, opted_in)
events(id, playbook_id, polygon, started_at, status)
call_results(id, event_id, person_id, status, attempt, transcript_summary, updated_at)
```

## Demo script (target ~3 min)

1. **Frame the problem (20s):** after a crisis, who is OK? Today = volunteers +
   spreadsheets, too slow.
2. **Draw the polygon (15s):** select a Tel Aviv neighborhood on the map.
3. **Trigger (10s):** fire `rocket_alert`; calls go out to ~30 real phones in the
   room.
4. **Watch it fill in (45s):** dots flip green/yellow as people answer; counters
   climb. Plant one volunteer who reports distress → red dot → emergency contact
   gets a call live.
5. **Close the loop with money (30s):** a planted NEEDS_HELP resident gets an SMS
   Payment Link / grant code, replies YES, and the dashboard shows the relief
   pool drop + "₪200 disbursed" — money over the phone, first hour. Meanwhile the
   usage meter shows the authority's invoice ticking up → "obvious who pays."
6. **Crisis-agnostic (20s):** swap to `earthquake.yaml` — "Tokyo, same engine,
   zero code."
7. **Close (15s):** opt-in + human-in-the-loop = trust; Dial moves the voice,
   Stripe moves the money — the first hour, at infinite scale.

## Known pitfalls

- **Webhook fields are guesses** — verify early or triage silently breaks.
- **Rate limits** — too high a concurrency cap gets calls throttled/dropped
  mid-demo. Tune `MAX_CONCURRENT_CALLS` against the real limit.
- **ngrok URL churn** — re-set `PUBLIC_BASE_URL` if the tunnel restarts.
- **Hebrew STATUS line** — the agent must say the line in the exact ASCII format;
  drill the prompt until it's reliable, or triage falls back to NEEDS_HELP.
- **Privacy** — store one-line summaries only, never full transcripts.
- **Stage phones on silent-but-vibrate** so 30 ringing phones don't drown the
  pitch.
- **Pre-stage everything** — polygon coordinates, playbook, seeded numbers — so
  the live run is one click.
- **Stripe stays in test mode** — use `sk_test_...` keys and Stripe's test cards;
  never commit a real key (`.env` only, `.env.example` with placeholders).
- **Don't let Stripe block the spine** — Layers A/B are additive. If the
  Dial green-dot milestone isn't solid, fix that before touching payments.
```
