import base64
import hashlib
import hmac
import os

from payments.store import OrderStatus, update_status, find_cart_by_source

WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET", "")


def verify_webhook(body: bytes, hmac_header: str) -> bool:
    """Verify the HMAC-SHA256 signature on a Shopify webhook request."""
    if not WEBHOOK_SECRET:
        return False

    digest = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode()
    return hmac.compare_digest(computed, hmac_header)


def _extract_cart_id(payload: dict) -> str | None:
    """
    Try to find the cart_id from the webhook payload.

    Shopify order webhooks include note_attributes, which we use to store
    the cart_id when creating the cart. Falls back to source_identifier lookup.
    """
    note_attributes = payload.get("note_attributes", [])
    for attr in note_attributes:
        if attr.get("name") == "cart_id":
            return attr.get("value")

    # Fallback: look up by source_identifier
    for attr in note_attributes:
        if attr.get("name") == "source_identifier":
            source = attr.get("value")
            if source:
                record = find_cart_by_source(source)
                if record:
                    return record.cart_id
    return None


def handle_order_creation(payload: dict) -> None:
    """
    Handle ORDERS_CREATE webhook.

    Shopify sends this after checkout completes and an order is created.
    """
    cart_id = _extract_cart_id(payload)
    if not cart_id:
        return

    order_id = str(payload.get("id", ""))
    update_status(cart_id, OrderStatus.COMPLETED, order_id=order_id)


def handle_order_payment(payload: dict) -> None:
    """
    Handle ORDER_TRANSACTIONS_CREATE webhook.

    Fired when a transaction is recorded against an order.
    """
    cart_id = _extract_cart_id(payload)
    if not cart_id:
        return

    order_id = str(payload.get("order_id", payload.get("id", "")))
    kind = payload.get("kind", "")
    status = payload.get("status", "")

    if kind == "capture" and status == "success":
        update_status(cart_id, OrderStatus.COMPLETED, order_id=order_id)
    elif status in ("failure", "error"):
        update_status(cart_id, OrderStatus.FAILED, order_id=order_id)


def handle_order_cancellation(payload: dict) -> None:
    """
    Handle ORDERS_CANCELLED webhook.

    Fired when an order is cancelled.
    """
    cart_id = _extract_cart_id(payload)
    if not cart_id:
        return

    order_id = str(payload.get("id", ""))
    update_status(cart_id, OrderStatus.CANCELLED, order_id=order_id)
