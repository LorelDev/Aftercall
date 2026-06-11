# Aftercall — Terms, Ethics & Compliance (hard rules)

**Purpose:** the operating terms every AI assistant and teammate MUST obey. These
are non-negotiable guardrails — a change that breaks one of these is wrong even
if it "works." Treat each `MUST` / `NEVER` as a gate.

> Scope note: this file captures (a) the project's own ethical/operating terms,
> documented across `README.md`, `docs/stack.md`, `docs/idea.md`, `docs/plan.md`,
> and (b) placeholders for the **official hackathon legal rules**, which are NOT
> in this repo and MUST be pasted in by a human (see §6). Do not assume the
> official rules say anything beyond what is written there.

---

## 1. The iron rule (product core, not a footnote)

- **MAY** let the agent offer **emotional support and reassurance** — that is the
  vehicle that gets people to answer and open up, and the conversation Aftercall
  mines for data.
- **NEVER** let the agent **diagnose, advise treatment, or act as a clinician**.
  It comforts and gathers data; the clinical help is always a human.
- **MUST** route every 🔴 DISTRESS case to a human: the operator is alerted and
  escalates with **one click** (emergency contact called / help dispatched).
- **NEVER** auto-close a red case. A human closes red.
- Money is a form of connection, not treatment: micro-grants connect people to
  resources, they do not "fix" anyone.

## 2. Consent & privacy

- **NEVER** call, SMS, or contact anyone not flagged `opted_in`. Opt-in is the
  whole basis of the system.
- **MUST** store transcripts as **one-line summaries only** — never the full
  transcript (`call_results.transcript_summary`).
- **MUST** keep personal data (phone, medical_notes, emergency contact) local to
  the SQLite DB; never log it to stdout in production paths or send it to a third
  party beyond Dial/Stripe as required to deliver the service.
- **NEVER** commit any real personal data or real demo phone numbers to git. Seed
  data lives in fixtures with fake numbers; real demo numbers stay local/`.env`.

## 3. Secrets & keys

- **MUST** keep all secrets in `.env`; commit only `.env.example` with placeholders.
- **NEVER** commit `DIAL_API_KEY`, `STRIPE_SECRET_KEY`, or any token.
- **MUST** run Stripe in **test mode** only (`sk_test_...`) for the hackathon; use
  Stripe test cards (e.g. `4242 4242 4242 4242`). **NEVER** a live Stripe key.
- If a key is ever committed by accident: rotate it immediately, then scrub.

## 4. Money handling (Stripe guardrails)

- **MUST** cap every disbursement; the relief pool has a hard ceiling
  (`STRIPE_RELIEF_POOL_CENTS`).
- **MUST** keep disbursement **policy-bound and audited** — humans set the policy,
  the agent only executes inside the guardrails.
- **NEVER** disburse outside an eligible, confirmed (`reply YES`) NEEDS_HELP flow.

## 5. Safe-conduct for AI assistants working in this repo

- **MUST** follow the project memory protocol in `CLAUDE.md` (PruneADE:
  `memory_search` before, `memory_write` after).
- **MUST NOT** change the frozen API contract or the status-line format
  (`docs/REQUIREMENTS.md` §5) without explicit human sign-off.
- **MUST** prefer cutting scope over breaking a `MUST` rule. If time is short,
  drop a `MAY`/`SHOULD` feature, never a guardrail.
- **MUST** flag, not silently "fix," anything that conflicts with these terms.

---

## 6. Official hackathon rules — CONFIRM AND FILL IN (do not assume)

These come from the Dial "My Agent Has a Phone" hackathon (Tel Aviv, June 2026)
and are **not** stored in this repo. A human MUST paste the authoritative text
here. Until then, treat each as UNKNOWN — do not invent the answer.

- [ ] **Eligibility** — team size limits, who may enter. (Repo assumes team of 3.)
- [ ] **Submission deadline** — exact time the build/repo must be frozen.
- [ ] **Submission deliverables** — repo? demo video? slides? live pitch length?
- [ ] **Sponsor-tool requirements** — required use of Dial (core) and any Stripe /
      sponsor minimums to qualify for prizes.
- [ ] **IP / ownership** — who owns the code after the event; any open-source
      requirement.
- [ ] **Data / privacy rules** imposed by the organizers beyond §2 above.
- [ ] **Fair-use / API limits** — any organizer-imposed rate or spend caps on Dial
      / Stripe credits.
- [ ] **Code of conduct** — link + any reporting requirements.

> When the human fills this in, convert each item into a `MUST`/`NEVER` line above
> the relevant section so it becomes an enforced gate, not just a note.
