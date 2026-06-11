# Aftercall

**The first hour after any crisis, at infinite scale.**

After any disaster — earthquake, hurricane, rocket alert, wildfire, building
power outage — no authority can quickly answer the one question that matters:
**who is OK and who is not?**

Today that answer is assembled by hand: volunteers, phone trees, spreadsheets.
It does not scale, and the first hour is the hour that counts.

**Aftercall** launches thousands of *parallel outbound AI voice calls* to an
opted-in population inside a geographic polygon, triages every answer, escalates
real distress to humans, and renders a live operations map for the authority.

> Built in 12 hours at the Dial *"My Agent Has a Phone"* hackathon — Tel Aviv,
> June 2026.

---

## Iron rule

**The agent NEVER treats anyone. It triages and connects.**

Every red case reaches a human: the emergency contact is called and a human
operator is alerted. The engine is **crisis-agnostic** — everything
crisis-specific lives in YAML playbooks. A Tokyo earthquake is a new playbook,
not new code.

This is not a safety footnote, it is the product: **opt-in only**, and
**human-in-the-loop escalation is a feature**.

---

## How it works

```
Trigger (POST /events {playbook, polygon})
  → dispatcher: load playbook → find opted-in people in polygon
    → build per-person Hebrew system prompt → parallel Dial voice calls
  → Dial webhook (POST /webhooks/dial):
      call.ended → triage.classify_call → save result → escalate if needed
      sms.received → "1" = OK, "2" = NEEDS_HELP
  → statuses:  OK 🟢  |  NEEDS_HELP 🟡  |  DISTRESS 🔴  |  UNREACHED ⚫
      DISTRESS  → call emergency contact + alert human operator
      UNREACHED → retry after 10 min (max 2) → SMS fallback
  → dashboard polls aggregate status → colored dots on a live map
```

The voice agent ends every call with a machine-readable line:

```
STATUS=<OK|NEEDS_HELP|DISTRESS> | SUMMARY=<one line>
```

`triage.classify_call()` parses it from the transcript. Anything unparsable is
treated conservatively as `NEEDS_HELP` and flagged for human review.

---

## Stack

| Layer       | Choice                                                        |
|-------------|---------------------------------------------------------------|
| Telephony   | [Dial](https://docs.getdial.ai) — outbound/inbound AI voice, SMS, webhooks (the core runtime) |
| Payments    | [Stripe](https://stripe.com) — readiness + usage billing ("who pays") and SMS-delivered emergency micro-grants |
| Backend     | Python 3.12 · FastAPI · SQLite (hackathon-grade, no auth)     |
| Dashboard   | Single-file HTML + Leaflet, polls status every 2s             |

**Dial is the spine** (outbound triage calls, escalation calls, inbound + outbound
SMS, inbound calls, event webhooks) and **Stripe rides on the phone layer** —
relief money moves over SMS in the first hour, which a screen-based app can't do
for people with no smartphone, data, or power. See [`docs/stack.md`](docs/stack.md).

---

## Quickstart

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # fill in DIAL_API_KEY
python -c "import models; models.init_db(); models.seed_demo_people()"
uvicorn app:app --reload --port 8000
```

Then open `dashboard/index.html` in a browser (it points at `http://localhost:8000`).

Trigger a run:

```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"playbook": "rocket_alert", "polygon": [[32.05,34.74],[32.10,34.74],[32.10,34.82],[32.05,34.82]]}'
```

---

## Repo layout

```
README.md                     this file
docs/ARCHITECTURE.md          full design (Hebrew)
docs/TASKS.md                 hour-by-hour plan + demo script
docs/HANDOFF.md               onboarding prompt for new contributors
backend/app.py                FastAPI: events API + Dial webhook receiver
backend/dispatcher.py         playbook load, prompt build, parallel calls
backend/triage.py             classify, escalate, retry, SMS fallback
backend/models.py             SQLite helpers + demo seed
backend/requirements.txt
backend/.env.example
playbooks/rocket_alert.yaml   demo scenario (Hebrew)
playbooks/earthquake.yaml     proves crisis-agnosticism
dashboard/index.html          Leaflet map + polling
```

---

## Ethics

Aftercall calls only people who have **opted in**. It never diagnoses, never
advises treatment, and never closes a red case automatically. Transcripts are
stored as one-line summaries only. The whole point of the system is to get a
human to the people who need one, faster.
