# Aftercall — Requirements (authoritative checklist)

**Purpose:** single source of truth for every requirement the project MUST meet.
Any AI assistant or teammate should read this and treat each `[ ]` as a gate. If
a change would violate one of these, stop and flag it. Sources are consolidated
from `README.md`, `docs/plan.md`, `docs/stack.md`, `docs/idea.md`, `docs/HANDOFF.md`.

> Legend: **MUST** = hard requirement, do not ship without it. **SHOULD** =
> strongly expected, cut only under explicit time pressure. **MAY** = optional.

---

## 1. Judging axes (what we are scored on — 10 pts each)

The whole build optimizes these three. Every feature should map to at least one.

### Axis 1 — Real-World Impact & Market Potential
- [ ] **MUST** reach real or simulated users over **voice and/or SMS** (not a mockup).
- [ ] **MUST** make "**who pays**" obvious and live on stage (Stripe — see §4).
- [ ] **SHOULD** frame a real buyer: authorities / NGOs / Home Front Command / campuses.

### Axis 2 — Technical Execution & Dial Integration Depth
- [ ] **MUST** use Dial as the **core runtime**, not a single API call (see §3).
- [ ] **MUST** handle latency / state / failure: concurrency cap + graceful
      UNREACHED → retry → SMS fallback + conservative triage fallback.

### Axis 3 — Innovation & Phone-Native Creativity
- [ ] **MUST** do something **impossible on a screen alone** — money moving over
      SMS/voice in the first hour, reaching people with no app/data/power.

---

## 2. Core product requirements (the spine)

- [ ] **MUST** trigger a run via `POST /events {playbook, polygon}`.
- [ ] **MUST** find **opted-in** people inside the polygon (point-in-polygon).
- [ ] **MUST** launch **parallel** outbound AI voice calls (not sequential).
- [ ] **MUST** triage every answer into `OK 🟢 | NEEDS_HELP 🟡 | DISTRESS 🔴 | UNREACHED ⚫`.
- [ ] **MUST** render a **live ops map** (Leaflet) that polls status every 2s.
- [ ] **MUST** be **crisis-agnostic**: everything crisis-specific lives in YAML
      playbooks — a new crisis is a new playbook, **not new code**.
- [ ] **MUST** ship ≥2 playbooks (`rocket_alert`, `earthquake`) to prove §above.

### Goal-of-the-day milestone (non-negotiable)
- [ ] **MUST** demonstrate: ONE real call → webhook → DB → a dot turns **green**
      on the live map. Everything past this is polish.

---

## 3. Dial integration depth — the 5 primitives

Dial is the spine. Aim to exercise all five; the first three are MUST.

- [ ] **MUST** Outbound voice (triage) — parallel calls; each ends with the
      machine-readable `STATUS=… | SUMMARY=…` line.
- [ ] **MUST** Event webhooks — `call.ended`, `sms.received`, delivery/status
      events drive the state machine (`POST /webhooks/dial`).
- [ ] **MUST** Outbound + inbound SMS — UNREACHED fallback ("reply 1 = OK, 2 =
      help"); inbound replies drive triage.
- [ ] **SHOULD** Outbound voice (escalation) — DISTRESS → automatic call to the
      person's emergency contact with a short Hebrew brief.
- [ ] **SHOULD** Inbound voice — a resident can call the Aftercall number back.

### Resilience the judges look for
- [ ] **MUST** `asyncio.Semaphore(MAX_CONCURRENT_CALLS)` tuned to the **real Dial
      rate limit** (verify in hour 0; too high → throttled mid-demo).
- [ ] **MUST** UNREACHED → retry (max 2, 10-min delay) → SMS fallback.
- [ ] **MUST** Unparsable-but-answered transcript → conservative `NEEDS_HELP` +
      human-review flag.

---

## 4. Stripe requirements (deferred, but required before the pitch)

Stripe is floating work (after the green dot), but to win Axis 1 it must be live.

- [ ] **SHOULD** Layer A — meter **usage per person reached** + show a visible
      invoice/Checkout ("obvious who pays" in one screen).
- [ ] **SHOULD** Layer B — ONE end-to-end micro-grant: NEEDS_HELP → Dial SMS
      Payment Link → reply YES → **test-mode** disbursement → shown on the map.
- [ ] **MAY** Layer C — live donation surge that converts to call capacity.
- [ ] **MUST** every disbursement is **capped, policy-bound, and audited** (humans
      set policy; the agent only executes inside guardrails).

---

## 5. Frozen API contract (do not change)

- [ ] `POST /events` body `{playbook, polygon}` → `{event_id}`
- [ ] `GET /events/{event_id}/status` → counters + dots
      `[{person_id, name, lat, lng, status}]`
- [ ] `POST /webhooks/dial` ← Dial events
- [ ] Status protocol line (exact ASCII): `STATUS=<OK|NEEDS_HELP|DISTRESS> | SUMMARY=<one line>`

### DB schema (SQLite)
```
people(id, name, phone, lang, lat, lng, age, medical_notes, emergency_contact_phone, opted_in)
events(id, playbook_id, polygon, started_at, status)
call_results(id, event_id, person_id, status, attempt, transcript_summary, updated_at)
```

---

## 6. Technical constraints

- [ ] **MUST** Python 3.12 · FastAPI · SQLite; dashboard = single-file HTML + Leaflet.
- [ ] **MUST** no auth / signup / production hardening (12-hour hackathon scope).
- [ ] **MUST** Hebrew voice prompts: calm, short, no drama; iterate on real people.
- [ ] **MUST** all secrets in `.env`; `.env.example` holds placeholders only.

---

## 7. Self-check before any commit / demo

An AI assistant should confirm ALL of these before claiming a task is done:

1. Does this still call **only opted-in** people? (§TOS)
2. Does the agent still **only triage/connect**, never treat? (§TOS iron rule)
3. Did I keep the **frozen contract** and status line exactly? (§5)
4. Did I avoid committing any real key? (§6, TOS)
5. Does this map to at least one **judging axis**? (§1)
6. If I touched Stripe, is it **test mode** and **capped**? (§4)
7. Is the **green-dot milestone** still intact / not regressed? (§2)
