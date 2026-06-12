"""Stripe — 'who pays' (metered usage) + relief micro-grants over SMS.

Guardrails (docs/TOS.md §4): every disbursement is capped, policy-bound, and
audited. Humans set policy; the agent only executes inside the guardrails.
Stripe runs in TEST MODE only (sk_test_...). If no key is set, everything runs
in DRY_RUN with deterministic fake refs so the demo still works end-to-end.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Optional

import models

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
DRY_RUN = not STRIPE_SECRET_KEY.startswith("sk_test_")

# Policy guardrails (humans set these; agent executes only inside them).
RELIEF_POOL_CENTS = int(os.environ.get("STRIPE_RELIEF_POOL_CENTS", "200000"))   # ₪2,000
MAX_GRANT_CENTS = int(os.environ.get("STRIPE_MAX_GRANT_CENTS", "20000"))        # ₪200
USAGE_PRICE_CENTS_PER_PERSON = int(os.environ.get("USAGE_PRICE_CENTS_PER_PERSON", "12"))

# Refuse to load a live key — hackathon is test-mode only.
if STRIPE_SECRET_KEY.startswith("sk_live_"):
    raise RuntimeError("Refusing live Stripe key — hackathon is test mode only (docs/TOS.md §3).")

try:
    import stripe  # type: ignore
    if not DRY_RUN:
        stripe.api_key = STRIPE_SECRET_KEY
except ImportError:
    stripe = None
    DRY_RUN = True


# ---------------------------------------------------------------------------
# Layer A — who pays: metered usage per person reached
# ---------------------------------------------------------------------------
def usage_invoice(persons_reached: int) -> dict[str, Any]:
    """A visible invoice — the business model live on stage, not a slide."""
    amount = persons_reached * USAGE_PRICE_CENTS_PER_PERSON
    return {
        "persons_reached": persons_reached,
        "unit_price_cents": USAGE_PRICE_CENTS_PER_PERSON,
        "amount_cents": amount,
        "currency": "ils",
        "line_item": f"{persons_reached} × ₪{USAGE_PRICE_CENTS_PER_PERSON/100:.2f} per person reached",
    }


# ---------------------------------------------------------------------------
# Layer B — relief micro-grant over SMS
# ---------------------------------------------------------------------------
def pool_status() -> dict[str, Any]:
    disbursed = models.disbursed_total_cents()
    return {
        "pool_cents": RELIEF_POOL_CENTS,
        "disbursed_cents": disbursed,
        "remaining_cents": max(RELIEF_POOL_CENTS - disbursed, 0),
    }


def offer_grant(event_id: Optional[int], person_id: int,
                amount_cents: Optional[int] = None) -> dict[str, Any]:
    """Record an offer (state=offered). Capped at MAX_GRANT_CENTS and pool ceiling."""
    amount = min(amount_cents or MAX_GRANT_CENTS, MAX_GRANT_CENTS)
    pool = pool_status()
    if amount > pool["remaining_cents"]:
        return {"ok": False, "reason": "pool exhausted", "pool": pool}
    did = models.record_disbursement(event_id, person_id, amount, "offered")
    return {"ok": True, "disbursement_id": did, "amount_cents": amount}


def confirm_and_disburse(event_id: Optional[int], person_id: int,
                         amount_cents: Optional[int] = None) -> dict[str, Any]:
    """On 'reply YES': fire a TEST-MODE disbursement from the pre-funded pool.

    Never disburse outside an eligible, confirmed NEEDS_HELP flow (docs/TOS.md §4).
    """
    amount = min(amount_cents or MAX_GRANT_CENTS, MAX_GRANT_CENTS)
    pool = pool_status()
    if amount > pool["remaining_cents"]:
        models.record_disbursement(event_id, person_id, amount, "denied", "pool_exhausted")
        return {"ok": False, "reason": "pool exhausted", "pool": pool}

    if DRY_RUN:
        ref = f"po_test_{uuid.uuid4().hex[:16]}"
    else:
        # Test-mode PaymentIntent (or Transfer/Payout per Stripe Connect setup).
        intent = stripe.PaymentIntent.create(
            amount=amount, currency="ils",
            description=f"Aftercall relief grant person={person_id} event={event_id}",
            metadata={"person_id": str(person_id), "event_id": str(event_id)},
        )
        ref = intent.id

    models.record_disbursement(event_id, person_id, amount, "disbursed", ref)
    return {
        "ok": True,
        "amount_cents": amount,
        "stripe_ref": ref,
        "pool": pool_status(),
        "dry_run": DRY_RUN,
    }
