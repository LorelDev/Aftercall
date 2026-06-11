# Aftercall — Full Stack & Monetization

This doc maps the Aftercall stack to the three hackathon judging axes and
explains how **Dial** (core) and **Stripe** (who-pays + phone-native money)
work together. Read alongside `docs/idea.md` and `docs/plan.md`.

## The judging axes (what we're optimizing for)

| # | Axis (10 pts each) | What wins it | Aftercall's answer |
|---|---|---|---|
| 1 | Real-World Impact & Market Potential | real/simulated users reached over voice/SMS, **obvious "who pays"** | authorities/NGOs reach an opted-in population; Stripe makes "who pays" live on stage |
| 2 | Technical Execution & **Dial Integration Depth** | Dial as core runtime across **multiple primitives**, latency/state/failure handled | 5 Dial primitives (below), concurrency cap, graceful UNREACHED→retry→SMS |
| 3 | Innovation & **Phone-Native Creativity** | interactions impossible on a screen alone | **money moving over SMS/voice in the first hour**, accessible to people with no app/power |

> Dial's own rule: you can't win an axis by treating the phone layer as an
> afterthought. So Dial is the spine, and Stripe rides *on* the phone layer, not
> beside it.

## Dial — the core runtime (criterion 2)

Aftercall uses Dial across **five primitives**, so the phone layer is the
product, not a single API call:

1. **Outbound voice (triage)** — thousands of parallel calls into the polygon;
   each ends with the machine-readable `STATUS=… | SUMMARY=…` line.
2. **Outbound voice (escalation)** — DISTRESS → an automatic call to the
   person's emergency contact with a short Hebrew brief.
3. **Outbound + inbound SMS** — UNREACHED fallback ("reply 1 = OK, 2 = help"),
   relief confirmations, donation receipts; inbound replies drive triage.
4. **Inbound voice** — a resident can call the Aftercall number back and reach
   their status / a human operator.
5. **Event webhooks** — `call.ended`, `sms.received`, delivery/status events
   drive the whole state machine.

Resilience that judges look for: `Semaphore(MAX_CONCURRENT_CALLS)` against the
real rate limit, UNREACHED → retry (max 2, 10-min) → SMS fallback, and an
unparsable transcript → conservative `NEEDS_HELP` + human-review flag.

## Stripe — "who pays" + phone-native money (criteria 1 & 3)

Stripe is layered so it is never cosmetic: it answers *who pays* **and** it does
something a screen can't — move relief money over the phone in the first hour.

### Layer A — Who pays (business model, criterion 1)

- **Readiness subscription (Stripe Billing):** municipalities, Home Front
  Command, campuses, and enterprises pay a recurring fee to keep Aftercall on
  standby for their opted-in population.
- **Usage / metered billing (Stripe metered subscriptions):** each event meters
  per *person reached*. Triggering a crisis run visibly accrues usage → an
  invoice. On stage this is the "obvious who pays" in one screen.

### Layer B — Closing the loop: emergency micro-grants (criteria 1 & 3)

The acute cases need a resource that costs money *now*: a ride to a shelter, a
hotel night, a medication refill, a generator, water. Aftercall closes the loop:

- The authority/NGO **pre-funds a relief pool** in Stripe.
- After triage, an eligible NEEDS_HELP case is offered a **pre-authorized
  micro-grant** — a **Stripe Payment Link** or a **single-use virtual card
  (Stripe Issuing)** — delivered **over SMS**, confirmed by reply ("reply YES to
  receive a ₪200 emergency grant for transport to a shelter").
- Every disbursement is **capped, policy-bound, and audited**. Humans set the
  policy; the agent only executes inside the guardrails.

This stays true to the **iron rule**: the agent *connects people to resources*,
it never treats. Money is a form of connection.

### Layer C — Optional live donation surge (demo wow)

A public **Stripe Payment Link / Checkout** funds a live event. Each donation
visibly converts into **call capacity + relief pool** on the ops map, and donors
get an SMS receipt via Dial. Phone-native: the donation *becomes* more calls.

## Accessibility angle (strengthens criteria 1 & 3)

Voice-first + SMS reaches exactly the people a web app misses in a disaster: the
elderly, people with no smartphone, people whose power/data is out. Single-use
card codes over SMS deliver relief to someone who is, in that moment, effectively
unbanked. This is "impossible on a screen alone," stated plainly.

## End-to-end flow (with Stripe)

```
Authority pays readiness (Stripe Billing) ──────────────┐
                                                        ▼
POST /events {playbook, polygon}  ── meters usage (Stripe) ──► invoice
  → Dial outbound voice triage (parallel)
  → webhook call.ended → triage → status
       OK 🟢
       NEEDS_HELP 🟡 ─ eligible? ─► offer micro-grant
                                     → Dial SMS (Payment Link / card code)
                                     → resident replies YES
                                     → Stripe disburses from relief pool (capped)
       DISTRESS 🔴 ─► Dial calls emergency contact + alerts operator
       UNREACHED ⚫ ─► retry ×2 → Dial SMS fallback (1/2)
  → dashboard: dots + counters + live relief-pool / disbursed totals
```

## Scope discipline for 12 hours

Build the spine first; add Stripe in this order and stop when time runs out:

1. **Dial spine** — one real outbound call → webhook → DB → green dot (the
   non-negotiable milestone).
2. **Stripe Layer A** — a single metered usage record + a visible
   invoice/Checkout so "who pays" is real, not a slide.
3. **Stripe Layer B** — one end-to-end micro-grant: NEEDS_HELP → SMS Payment
   Link → confirm → test-mode disbursement, shown on the dashboard.
4. **Layer C donation surge** — only if there's time; it's a nice closer, not the
   point.

Everything Stripe runs in **test mode** with placeholder keys in `.env`
(`STRIPE_SECRET_KEY`), same discipline as the Dial key. Never commit real keys.

## Required env (additions)

```
DIAL_API_KEY=sk_live_...
MAX_CONCURRENT_CALLS=10
PUBLIC_BASE_URL=https://<ngrok>.ngrok.io
STRIPE_SECRET_KEY=sk_test_...
STRIPE_RELIEF_PRICE_ID=price_...      # metered usage price
STRIPE_RELIEF_POOL_CENTS=500000       # demo relief pool cap
```

## One-line "who pays" for the pitch

> Authorities and NGOs pay Aftercall a readiness subscription plus usage per
> person reached; the same rails disburse capped emergency micro-grants over SMS
> in the first hour — money that moves at the speed of the phone, not the app.
