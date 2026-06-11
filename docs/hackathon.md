# Aftercall — Hackathon Strategy (Dial "My Agent Has a Phone")

Tel Aviv, June 11 (6:00 PM) – June 12 (10:00 AM), 2026. This file maps our build
to how we're actually judged, and pins the submission mechanics so nothing is
improvised at the buzzer. Sources: getdial.ai/hackathon + docs.getdial.ai.

## Judging criteria (3 × 10 = 30 pts, averaged across judges)

1. **Real-World Impact & Market Potential** — authentic problem, real user
   demand, clear monetization. Rewards *demonstrable user engagement over
   voice/SMS* plus a *transparent revenue model*. Low scores = gimmicky / value
   disconnected.
2. **Technical Execution & Depth of Dial Integration** — Dial as the
   architectural backbone, multiple primitives orchestrated (inbound/outbound
   calls, SMS, event handling), production concerns (latency, failure modes).
   Low scores = brittle demo where Dial could be swapped out.
3. **Innovation & Phone-Native Creativity** — would the concept still be
   compelling *without* voice/SMS? Rewards genuinely novel phone-native
   interaction.

## Our self-assessment

- **Criterion 2 (Dial depth) — our strongest.** We use every primitive:
  outbound triage voice, escalation voice, inbound + outbound SMS, inbound
  calls, webhooks. The Semaphore fan-out + UNREACHED retry + SMS fallback *is*
  the latency/failure-mode story. Risk to avoid: "Dial easily substituted" —
  emphasize the AI voice agent conducting a genuine **emotional-support
  conversation** that doubles as the data-collection instrument, plus inbound SMS
  reply/OTP capture — not a dumb dialer.
- **Criterion 3 (phone-native) — also very strong.** The test is "compelling
  without voice/SMS?" Aftercall reaches people with *no smartphone, no data, no
  power* — a screen app reaches zero of them in a blackout. And the phone-native
  magic is **emotional support at population scale**: a calm, human-like voice
  reaching thousands at once and turning each conversation into situational data
  no web form could collect.
- **Criterion 1 (impact / who pays) — thinnest on the exact rubric.** 30 real
  phones answering = the engagement half. Stripe readiness subscription +
  metered usage invoice ticking live = the revenue half. Risk: disaster response
  reads as hard-to-monetize / government-sales — make the readiness-subscription
  framing inevitable, live on stage, not a slide.

## De-risk the spine with the GetDial playbooks repo

`github.com/GetDial-AI/playbooks` is **runnable reference code** (not our crisis
YAML). Its "SMS & Voice — call placement and event streaming" example is the
ground truth for the request body + webhook payload field names we currently
*guess* (`type`/`answered`/`transcript`/`metadata.person_id`). **Hour 0: copy
those shapes verbatim into `dispatcher.place_call()` and the `/webhooks/dial`
parser** before building features. Skip the self-hosted-LLM-over-WebSocket and
LangChain examples — over-scope for 12h; our FastAPI fan-out is more robust.

Naming caution: their "playbooks" = reference code; our "playbooks" = crisis
YAML. Keep them distinct in the pitch.

## Submission deliverables (lock early, not at the buzzer)

- **Public GitHub repo** — judges read code without auth, so README quality and
  the primitive enumeration carry criterion 2.
- **Demo video ≤ 1 minute** (Loom / YouTube / Vimeo, publicly viewable). This is
  a *separate artifact* from the 3-min stage demo. Record a tight 60s screen
  capture with hard cuts + captions during the freeze hour: trigger → dots
  flipping → one red escalation call → money-over-SMS confirmation. Let captions
  carry it so every Dial primitive is visible without narration.
- **Project description ≤ 280 chars** (draft below).
- Team LinkedIn URLs (one per member), one contact email.

### 280-char description (draft — 274 chars, fits)

> Aftercall phones thousands of opted-in people in a crisis polygon. A calm AI
> voice gives emotional support and turns each conversation into live situational
> data - OK, needs help, or distress - escalating red cases to a human. The first
> hour after any crisis. Built on Dial.
