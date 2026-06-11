# Aftercall — Functionality Spec

> **One-line pitch:** Aftercall is an AI that gathers real-time situational data
> after a crisis at population scale — reaching each person as a calm, caring voice
> and turning every supportive conversation into live awareness for the authority.

**What it does, in one breath:** after any disaster, Aftercall fires thousands of
*parallel outbound AI voice calls* to an opted-in population inside a map polygon.
Each call reaches the person as **emotional support** — a calm voice that asks how
they are and reassures them — and that very conversation is the instrument that
**collects the data**: every answer becomes a status (OK / needs help / distress)
plus a one-line summary, aggregated into a live operations map for the authority.
The support is what gets people to answer and open up; the gathered data is what
saves the response — **the first hour after any crisis, at infinite scale.**

This file is the functional source of truth: *what the system does* and *why*.
For the verified telephony API see [`DIAL.md`](DIAL.md); for hard rules see
[`REQUIREMENTS.md`](REQUIREMENTS.md) and [`TOS.md`](TOS.md); for who builds what
see [`TASKS.md`](TASKS.md); for judging strategy see [`hackathon.md`](hackathon.md).

---

## 1. Guiding principles (non-negotiable, designed-in)

These are not safety footnotes — they are the product.

1. **Opt-in participation.** Aftercall only ever contacts people who have
   explicitly opted in (`people.opted_in`). No cold outreach, ever.
2. **Privacy by design.** Only one-line summaries of calls are stored
   (`transcript_summary`), never full transcripts. Personal data stays in the
   local DB and is shared with no third party beyond what Dial/Stripe need to
   deliver the service.
3. **Human-in-the-loop escalation.** Every 🔴 distress case reaches a human: the
   operator is alerted and escalates with **one click** — calling the emergency
   contact / dispatching help. Red cases are never auto-closed; a human owns them.
4. **AI does not replace professionals.** The agent offers **emotional support and
   reassurance**, but it never diagnoses, never advises treatment, and never acts
   as a clinician or first responder. It comforts and gathers data, then connects a
   human — it is not the clinical help itself.
5. **Full transparency.** The ops map, live counters, the machine-readable status
   protocol, the metered-usage invoice, and the audited disbursement log mean
   every action the system takes is visible and accountable.

---

## 2. Actors

| Actor | Role |
|---|---|
| **Authority / NGO operator** | triggers an event, watches the ops map, takes over red cases. Pays the readiness subscription + metered usage. |
| **Resident (opted-in citizen)** | receives the AI voice call / SMS, answers status, may receive a relief micro-grant. |
| **Emergency contact** | a resident's pre-listed contact, auto-called when that resident is in distress. |
| **AI voice agent (Dial)** | conducts each call as a calm, supportive conversation from a per-person system prompt; gathers the person's status and ends with the status line. Offers comfort, never clinical treatment. |
| **Human responder** | the person the operator dispatches once a red case is surfaced. |

---

## 3. End-to-end functional flow

```
Operator triggers an event (playbook + map polygon)
  → Aftercall loads the crisis playbook (YAML) and finds opted-in residents in the polygon
    → builds a per-person Hebrew system prompt
    → places parallel AI voice calls via Dial (concurrency-capped)
  → Dial streams events back via webhook:
      call.ended         → fetch transcript → classify → save status → escalate if needed
      message.received   → inbound SMS reply drives status ("1"=OK, "2"=NEEDS_HELP) / grant confirm
  → each resident lands in one status:
      OK 🟢   |   NEEDS_HELP 🟡   |   DISTRESS 🔴   |   UNREACHED ⚫
      DISTRESS  → alert operator → one-click escalation (emergency contact / dispatch help)
      NEEDS_HELP→ (eligible) offer relief micro-grant over SMS
      UNREACHED → retry after 10 min (max 2) → SMS fallback
  → live dashboard polls aggregate status every 2s → colored dots + counters on a map
  → metered usage accrues per person reached → a visible invoice ("who pays")
```

---

## 4. Feature catalog

### 4.1 Event trigger & population targeting
- Operator fires a run: `POST /events {playbook, polygon}` → `{event_id}`.
- The system resolves **who to call**: opted-in residents whose `(lat,lng)` falls
  inside the polygon (point-in-polygon query).
- **Crisis-agnostic:** all crisis-specific content (the prompt, escalation copy,
  thresholds) lives in a **YAML playbook**. A new crisis = a new playbook, *zero
  code* (`rocket_alert.yaml`, `earthquake.yaml` ship to prove this).

### 4.2 Outbound AI support call — the conversation that gathers the data (the core)
- For each target, build a **per-person Hebrew system prompt** (name, context,
  calm/short/no-drama tone) and place a Dial AI voice call that opens as
  **emotional support** — checking in, reassuring, listening.
- The agent holds a genuine supportive conversation and, from what the person
  says, derives their situation — ending every call with the exact
  machine-readable line:
  ```
  STATUS=<OK|NEEDS_HELP|DISTRESS> | SUMMARY=<one line>
  ```
- **Parallel fan-out** under `asyncio.Semaphore(MAX_CONCURRENT_CALLS)`, tuned to
  Dial's real rate limit so the demo never gets throttled.

### 4.3 Triage classification
- On `call.ended`, fetch the transcript (`GET /api/v1/calls/{id}` — the webhook
  carries no inline transcript, see `DIAL.md`) and `classify_call()` regex-parses
  the STATUS line into a status.
- **Conservative fallback:** answered but unparsable → `NEEDS_HELP` + human-review
  flag (never silently mark someone OK).
- Not answered / `status != completed` / `canceled` → `UNREACHED`.

### 4.4 Status model
| Status | Meaning | System action |
|---|---|---|
| `OK 🟢` | resident confirmed safe | record, show green dot |
| `NEEDS_HELP 🟡` | non-acute need | record; if eligible, offer relief micro-grant over SMS |
| `DISTRESS 🔴` | acute distress | **escalate to a human** (see 4.5) |
| `UNREACHED ⚫` | no contact | retry ×2 (10-min) → SMS fallback |

### 4.5 Human-in-the-loop escalation
- `DISTRESS` raises an **operator alert** on the dashboard with a **one-click
  action** to escalate: place the outbound Dial voice call to the resident's
  emergency contact (short Hebrew brief) / dispatch help. The human, not the agent,
  pulls the trigger.
- A human owns the red case from there. The agent does not treat or close it.

### 4.6 Unreached recovery (resilience)
- `UNREACHED` → automatic **retry** (max 2 attempts, 10-minute delay).
- Still unreached → **SMS fallback**: "reply 1 = OK, 2 = needs help."
- Inbound `message.received` with `body` `1`/`2` updates the resident's status —
  closing the loop for people who can't take a call.

### 4.7 Inbound channels
- **Inbound SMS:** residents reply to drive their own status / confirm a grant.
- **Inbound voice:** a resident can call the Aftercall number back to reach their
  status or a human operator.

### 4.8 Live operations map (situational awareness)
- Single-file Leaflet dashboard. Operator **draws the polygon**, fires the event,
  and watches **colored dots flip** (🟢🟡🔴⚫) with **live counters**.
- Polls `GET /events/{event_id}/status` every 2s for aggregate state + per-person
  dots `[{person_id, name, lat, lng, status}]`.

### 4.9 Money over the phone (Stripe — relief + "who pays")
Phone-native by design: money moves to people with no app, data, or power.
- **Who pays (Layer A):** a **readiness subscription** for authorities/NGOs, plus
  **metered usage per person reached** that visibly accrues into an invoice — the
  business model is live on stage, not a slide.
- **Relief micro-grants (Layer B):** an eligible `NEEDS_HELP` resident is offered
  a **pre-authorized grant over SMS** (Stripe Payment Link / single-use code);
  they **reply YES**, a **test-mode disbursement** fires from a pre-funded relief
  pool, and the dashboard shows the pool drop + "₪200 disbursed."
- **Guardrails:** every disbursement is **capped, policy-bound, and audited** —
  humans set policy, the agent only executes inside it.
- **Donation surge (Layer C, optional):** public donations convert live into call
  capacity + relief pool; donors get an SMS receipt.

---

## 5. Data model (SQLite)

```
people(id, name, phone, lang, lat, lng, age, medical_notes,
       emergency_contact_phone, opted_in)
events(id, playbook_id, polygon, started_at, status)
call_results(id, event_id, person_id, status, attempt,
             transcript_summary, updated_at)
```
- **Correlation:** the Dial webhook has no `metadata`, so Aftercall stores a
  `callId → person_id` map at call-placement time to tie each result back to a
  person (see `DIAL.md`).

## 6. Public interface (frozen contract)

- `POST /events` `{playbook, polygon}` → `{event_id}`
- `GET /events/{event_id}/status` → counters + per-person dots
- `POST /webhooks/dial` ← Dial events (`call.ended`, `message.received`,
  `call.transcript.ready`)

## 7. Non-functional behaviour

- **Concurrency & failure modes:** semaphore-capped fan-out; retry→SMS fallback;
  conservative triage on ambiguity — the resilience story for judging axis 2.
- **Latency:** dashboard reflects new statuses within one 2s poll of the webhook.
- **Hackathon scope:** no auth/signup, no production hardening; secrets in `.env`,
  Stripe strictly in test mode.

## 8. Explicitly out of scope

- No diagnosis, triage advice, or treatment by the AI.
- No automatic closing of red cases.
- No contact with anyone not opted in.
- No storage of full transcripts.
- No real-money Stripe flows during the hackathon (test mode only).
