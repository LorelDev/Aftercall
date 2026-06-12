# Aftercall — Handoff Prompt

Paste everything below into a fresh Claude Code session started in `/Users/ori/Downloads/Aftercall`.

---

You are continuing work on **Aftercall**, a hackathon crisis-response platform (Dial "My Agent Has a Phone" hackathon, Tel Aviv, June 2026). The system places parallel outbound AI voice calls (in Hebrew) to residents after an emergency, collects essential info wrapped in emotional support, triages each call (OK / NEEDS_HELP / DISTRESS / UNREACHED), and maps results live on an operator dashboard. The repo docs are in `docs/` (functionality.md, DIAL.md, REQUIREMENTS.md, TOS.md, TASKS.md, hackathon.md) — read them if you need deeper context.

## Current state (everything below is BUILT and WORKING live)

- **Dial account is live.** Real number: +19087425364, `DIAL_FROM_NUMBER_ID=cmq9zwf6i001815ndtx7fnzk6`. API key is in `backend/.env` (`DIAL_API_KEY=sk_live_...`, originally from `~/.local/share/dial/auth.v1.json`). Real test calls to the user at +972552285564 have succeeded end-to-end.
- **Dial API facts (verified live, differ slightly from docs):**
  - Base `https://getdial.ai/api/v1`, Bearer auth. `POST /calls {to, fromNumberId, outboundInstruction, language}`, `GET /calls/{id}`, `POST /messages`.
  - Live responses are wrapped: `{"ok":true,"call":{...}}` — handled by `_unwrap()` in `backend/dial_client.py`.
  - `status` on a fetched call is a dict: `{state, terminationType, ...}` (states like Queued/Ringing/Terminated; terminationType "completed").
  - Transcript is a plain string of `User: ...\nAgent: ...` turns.
  - Webhooks (`call.ended`, `message.received`) carry **no metadata** — correlation lives in the `call_map` table (call_id → person_id/event_id), persisted at call placement. Never lose this.
- **Listen daemon** (launchd `ai.getdial.listen.plist`) is installed and forwards Dial webhooks to local target `http://localhost:8000/webhooks/dial`. A reconciliation poller (`dispatcher.reconcile_call`) also polls Dial directly as webhook-independent backup.
- **Backend** (`backend/`, Python 3.12 venv at `backend/.venv`): FastAPI on **port 8000**, SQLite. Key files: `app.py` (routes: POST /events, POST /campaigns, GET /events/{id}/status, POST /webhooks/dial, GET /playbooks, GET /health), `dispatcher.py`, `dial_client.py` (DRY_RUN mode when no API key), `triage.py` (parses last `STATUS=<...> | SUMMARY=<...>` line; unparsable → NEEDS_HELP; DISTRESS → escalation call to emergency contact + operator alert; UNREACHED → retry x2 then SMS fallback), `models.py`.
- **Dashboard**: `dashboard/live.html`, RTL Hebrew, served on **port 8090** (port 8080 is taken by a foreign service). Operator enters phone numbers + names, one button (`📞 התקשר לכולם עכשיו`) fires POST /campaigns → parallel real calls. Leaflet map with live status dots, polls `/events/{id}/status` every 2s. The Stripe/"קרן סיוע" section was removed per user request.
- **Playbooks**: `playbooks/wellbeing_check.yaml` was JUST rewritten to fix a real observed bug where the agent read the system prompt aloud ("1. ... 2. ... 3. ..."). New prompt enforces: live two-way conversation, never read instructions/headings/numbering aloud, one question at a time, warm tone, and a mandatory final machine line `STATUS=<OK|NEEDS_HELP|DISTRESS> | SUMMARY=<one Hebrew sentence>` spoken quietly after the farewell. `rocket_alert.yaml` and `earthquake.yaml` still use the OLD prompt style and may need the same conversational fix.

## Active task (in progress — user's latest request, 4 parts)

1. ✅ Fix the agent reading the prompt aloud (wellbeing_check.yaml rewritten; optionally port to the other two playbooks).
2. ⬜ Save full chat transcripts to **Supabase**.
3. ⬜ Make sure info updates live on the dashboard.
4. ⬜ Refine the dashboard design.

### Planned next steps (follow this plan)
- Add a `transcript` column to `call_results` in `backend/models.py` (idempotent `ALTER TABLE` migration — DB already exists with data).
- In `triage.classify_call`, save the normalized transcript string after `fetch_call`.
- Create `backend/supabase_store.py`: httpx POST to `{SUPABASE_URL}/rest/v1/{table}` with `apikey` + `Authorization: Bearer` headers; **graceful no-op when SUPABASE_URL/SUPABASE_KEY are unset** (they are NOT configured yet — ask the user for the project URL + service-role key, and give them the CREATE TABLE SQL to run). Wire it into classify_call.
- Note to user once: docs/TOS.md says store only one-line summaries; saving full transcripts to Supabase is the user's explicit choice and overrides this — flag it briefly, don't block.
- Expose transcript + summary in `GET /events/{id}/status` and show them in `dashboard/live.html` (expandable cards or modal on the intake cards).
- Refine the dashboard design while you're in there.
- Restart uvicorn (port 8000) and verify end-to-end with a real call to +972552285564 (ask the user before placing real calls).

## Operational gotchas
- Non-interactive shells lack Homebrew PATH: prefix commands with `export PATH="/opt/homebrew/bin:$PATH"` (needed for `npx`, `gh`, etc.). Dial CLI: `npx -y @getdial/cli@latest`.
- System Python is 3.9 — always use `backend/.venv` (built from `/opt/homebrew/bin/python3.12`).
- Run backend: `cd backend && .venv/bin/uvicorn app:app --port 8000`. Dashboard: any static server on 8090 from `dashboard/`.
- `pkill`ing old uvicorn/poll loops shows background-task exit 144 — expected, ignore.
- Dial endpoints are NOT idempotent — a retried POST places a second call. Confirm failure before retrying.
- The user communicates in Hebrew and English; UI and call content are Hebrew (he-IL).

## Iron rules
- Only call opted-in people; the agent triages and connects — it never diagnoses or treats.
- Never lose the call_id → person mapping (webhooks have no metadata).
- DISTRESS in doubt → prefer severity (NEEDS_HELP).
