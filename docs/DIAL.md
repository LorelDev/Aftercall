# Dial — verified API reference (the spine)

**What Dial is:** a "communication stack for AI agents." It **provisions real
phone numbers** to your agent and lets it make/receive **voice calls, SMS, and
WhatsApp** over one REST API (plus Python/Node SDKs, a CLI, and an MCP server).
It is **not just a gateway** — you own a provisioned number with local caller ID
that residents can call/text back.

> Verified against https://docs.getdial.ai and https://getdial.ai (June 2026).
> A few payload shapes the public docs 404'd on are marked **VERIFY LIVE** —
> confirm these against the real API in hour 0.

## What you get on signup

- A **provisioned phone number** (US / Canada / international), in seconds —
  identified as a `fromNumberId` like `pn_123`.
- **$5 free credit**, no credit card to start.
- An **API key** `sk_live_...` (Bearer auth), one account.
- Access via **REST**, **SDK** (`@getdial/sdk`, Python), **CLI**, or **MCP**.

## Auth & base URL

```
Base URL:  https://getdial.ai/api/v1
Header:    Authorization: Bearer sk_live_...
           Content-Type: application/json
```

## Primitive 1 — Place an AI voice call

`POST /api/v1/calls`

```json
{
  "to": "+14155550123",
  "fromNumberId": "pn_123",
  "outboundInstruction": "<system prompt that drives the AI agent's conversation>",
  "language": "en-US"
}
```

Response (immediate): `{ "id": "call_...", "status": "initiated" }`. The AI agent
then runs the call from `outboundInstruction`.

- ⚠️ **NOT idempotent** — a retry places a *second* call. Confirm failure before retry.
- ⚠️ The body has **no `metadata` / `clientReference` field** (VERIFY LIVE). To map
  a call back to a person, **store `callId → person_id` when you place the call.**

## Primitive 2 — Send SMS

`POST /api/v1/messages`

```json
{ "to": "+14155550123", "fromNumberId": "pn_123", "body": "Hello from Dial" }
```

Response: `{ "id": "msg_...", "status": "queued" }`. Also **not idempotent**.

## Primitive 3 — Webhooks (the event stream)

Register an HTTPS `targetUrl` + `eventTypes` (`["*"]` or an explicit list). Every
delivery carries headers:

- `X-Dial-Event-Type` — the event type
- `X-Dial-Event-ID` — unique per event → **dedupe on this**
- `X-Dial-Signature` — HMAC → **verify it**

Event envelope (shared): `{ id, object:"event", type, version, createdAt, relatedObject, data }`.

### Event types

| Event | Meaning |
|---|---|
| `call.ended` | a voice call (inbound or outbound) finished |
| `message.received` | an inbound SMS arrived on your number |
| `call.transcript.ready` | a call's transcript is ready to fetch |
| `webhook.ping` | test event |

### `call.ended` payload (REAL)

```json
{
  "type": "call.ended",
  "data": {
    "callId": "call_01HW...",
    "from": "+14155550123",
    "to": "+14155559876",
    "direction": "inbound",
    "durationSeconds": 47,
    "status": "completed",
    "canceled": false,
    "transcriptAvailable": true
  }
}
```

There is **no inline `transcript`**, **no `metadata`**, and **no `answered`** field.
Fetch the transcript separately after the event (`GET /api/v1/calls/{id}` —
VERIFY LIVE for the exact transcript shape).

### `message.received` payload (REAL)

```json
{
  "type": "message.received",
  "data": {
    "messageId": "msg_01HW...",
    "from": "+14155550123",
    "to": "+14155559876",
    "channel": "sms",
    "body": "1",
    "source": "external"
  }
}
```

---

## Corrections vs. the original plan (field names were guesses)

The plan/HANDOFF flagged the webhook fields as guesses. Confirmed — they were
wrong. Build against the table below, not the guesses.

| Original guess | Reality | What to do |
|---|---|---|
| event `sms.received` | **`message.received`** | rename everywhere |
| inline `transcript` on webhook | **not present**; only `transcriptAvailable` | on `call.ended` → fetch the call → then `classify_call()` |
| `metadata.person_id` on webhook | **no `metadata` exists**; place-call has no metadata param | **store `callId → person_id` at placement**; fall back to matching `to` |
| `answered` boolean | no such field | branch on `status` (`completed`) + `canceled` for UNREACHED |
| `type` at top level | top-level `type`, payload fields under **`data`** | read `data.*` |

### Impact on tasks
- **Task 1 (Dial):** persist a `callId → person_id` map at call-placement time.
- **Task 2 (Triage):** `classify_call()` is **two steps** — fetch transcript via
  `GET /api/v1/calls/{id}`, then regex the `STATUS=… | SUMMARY=…` line. Inbound
  SMS handler keys off `message.received` + `data.body` (`1`=OK, `2`=NEEDS_HELP).

## Hour-0 VERIFY-LIVE checklist

- [ ] Exact transcript JSON shape from `GET /api/v1/calls/{id}` (string vs turns).
- [ ] Confirm no `metadata`/`clientReference` accepted on `POST /calls` (else use it).
- [ ] Real **rate limit** → set `MAX_CONCURRENT_CALLS`.
- [ ] Whether `call.transcript.ready` is more reliable than `call.ended` for triage timing.
- [ ] WhatsApp setup (if used) vs SMS-only.

## Sources

- https://getdial.ai
- https://docs.getdial.ai
- https://docs.getdial.ai/documentation/capabilities/place-a-voice-call
- https://docs.getdial.ai/documentation/platform/webhooks
- https://docs.getdial.ai/api-reference/events/overview
