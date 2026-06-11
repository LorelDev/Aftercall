# Aftercall — Idea

**One-liner:** "The first hour after any crisis, at infinite scale."

## The problem

After any disaster — earthquake, hurricane, rocket alert, wildfire, a building
losing power — one question decides where help goes: **who is OK and who is
not?**

Right now that answer is assembled by hand. Volunteers work phone trees,
municipalities pass around spreadsheets, families call families. It is slow, it
does not scale, and the first hour — the hour that matters most — is spent
finding out *where* the problem is instead of *fixing* it.

## The idea

**Aftercall** is a crisis-agnostic engine that, on a single trigger, launches
**thousands of parallel outbound AI voice calls** to an opted-in population
inside a geographic polygon. It:

1. Calls everyone in the affected area at once.
2. Triages every answer into **OK / NEEDS_HELP / DISTRESS / UNREACHED**.
3. Escalates real distress to humans automatically.
4. Renders a **live operations map** so the authority sees the situation fill in
   in real time.

What took a room of volunteers a day now takes minutes, and the humans are freed
to do the one thing only humans can: respond.

## The iron rule

**The agent NEVER treats anyone. It triages and connects.**

- Every red (DISTRESS) case reaches a human — the person's emergency contact is
  called and a human operator is alerted. A red case is never auto-closed.
- The agent gives no medical advice and makes no diagnosis.
- Calls go only to people who have **opted in**.

This is not a disclaimer bolted on the side — it is the product. Opt-in and
human-in-the-loop escalation are **features**, and they are the reason an
authority can trust the system.

## Why it's crisis-agnostic

The engine knows nothing about any specific disaster. Everything
crisis-specific — the opening line, the questions, the tone — lives in a YAML
**playbook**. A rocket alert in Tel Aviv and an earthquake in Tokyo are the same
engine with a different playbook and **zero code changes**. That is the global
story: deploy once, adapt everywhere by writing a file.

## How a call works

Each person gets a short, calm, Hebrew voice call from the agent. The agent
checks their status and ends every call with one machine-readable line:

```
STATUS=<OK|NEEDS_HELP|DISTRESS> | SUMMARY=<one line>
```

The backend parses that line to triage the person. If the line can't be parsed,
the person is conservatively marked NEEDS_HELP and flagged for a human — the
system always errs toward sending help, never toward silence.

## What the audience sees

A single live map. A polygon is drawn over a neighborhood, calls fire, and dots
turn green / yellow / red / grey as answers come back, with running counters
above. The demo lives or dies on this screen — it is the entire pitch in one
glance: *the first hour, visualized, at scale.*

## Who pays — and closing the loop (Stripe)

Triage isn't the end. The most acute cases need a **resource that costs money in
the first hour** — a ride to a shelter, a hotel night, a medication refill, a
generator, water. Aftercall closes the loop:

- **Who pays:** authorities, Home Front Command, campuses, and NGOs pay a
  **readiness subscription** (Stripe Billing) plus **usage per person reached**
  (Stripe metered billing). Triggering a run visibly accrues an invoice — the
  "obvious who pays" is live on stage, not a slide.
- **Emergency micro-grants over SMS:** the authority/NGO pre-funds a relief pool
  in Stripe; after triage, an eligible `NEEDS_HELP` case is offered a
  **pre-authorized, capped micro-grant** — a Stripe Payment Link or single-use
  virtual card — delivered **over SMS** and confirmed by reply. Humans set the
  policy; the agent only executes inside the guardrails.

This is still the iron rule: the agent **connects people to resources**, it never
treats. Money is a form of connection — and moving it over the phone in the first
hour is something a screen-based app can't do for people with no smartphone, no
data, or no power. Full detail in [stack.md](./stack.md).

## Pitch framing

- **Trust:** opt-in only; a human owns every red case.
- **Scale:** thousands of parallel calls vs. a phone tree.
- **Global:** same engine, different playbook — a new disaster is a new YAML
  file, not a new project.
- **Phone-native money:** relief moves over SMS/voice in the first hour —
  impossible on a screen alone (see [stack.md](./stack.md)).

## Context

Built in 12 hours at the Dial *"My Agent Has a Phone"* hackathon — Tel Aviv,
June 2026, team of 3. Telephony by [Dial](https://docs.getdial.ai).
