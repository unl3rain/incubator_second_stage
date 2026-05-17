from __future__ import annotations

from fastapi import HTTPException

from app.core.config import settings
from app.services.entitlements import activate_pro_entitlement

PLAN_PRICE_LOOKUP = {
    "pro_monthly": settings.stripe_price_pro_monthly,
    "pro_yearly": settings.stripe_price_pro_yearly,
}


def create_checkout_session(profile_id: str, plan: str) -> dict:
    if plan not in PLAN_PRICE_LOOKUP:
        raise HTTPException(status_code=422, detail="Unsupported billing plan")

    if settings.billing_mock_mode or not settings.stripe_secret_key:
        activate_pro_entitlement(profile_id, plan)
        return {
            "checkout_url": f"{settings.stripe_success_url}&profile_id={profile_id}&plan={plan}",
            "mode": "mock",
        }

    price_id = PLAN_PRICE_LOOKUP.get(plan)
    if not price_id:
        raise HTTPException(status_code=500, detail=f"Missing Stripe price ID for plan: {plan}")

    try:
        import stripe  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Stripe SDK unavailable: {exc}") from exc

    stripe.api_key = settings.stripe_secret_key

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.stripe_success_url,
        cancel_url=settings.stripe_cancel_url,
        client_reference_id=profile_id,
        metadata={"profile_id": profile_id, "plan": plan},
    )

    return {
        "checkout_url": session.url,
        "mode": "stripe",
    }


def handle_webhook(raw_body: bytes, signature: str | None) -> dict:
    if settings.billing_mock_mode:
        return {"ok": True}

    if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
        raise HTTPException(status_code=500, detail="Stripe is not configured")

    try:
        import stripe  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Stripe SDK unavailable: {exc}") from exc

    stripe.api_key = settings.stripe_secret_key
    try:
        event = stripe.Webhook.construct_event(raw_body, signature, settings.stripe_webhook_secret)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid webhook signature: {exc}") from exc

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        profile_id = data_object.get("client_reference_id") or data_object.get("metadata", {}).get("profile_id")
        plan = data_object.get("metadata", {}).get("plan", "pro_monthly")
        if profile_id:
            activate_pro_entitlement(profile_id, plan)

    return {"ok": True}
