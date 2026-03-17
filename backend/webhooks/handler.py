
import base64
import hashlib
import hmac
import os

from payments.store import PaymentStatus, update_status

WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET", "")

# Topics that map to a terminal payment outcome
_TOPIC_STATUS: dict[str, PaymentStatus] = {
    "payment_sessions/resolve": PaymentStatus.COMPLETED,
    "payment_sessions/reject": PaymentStatus.FAILED,
}


def verify_webhook(body: bytes, hmac_header: str) -> bool:
    
    if not WEBHOOK_SECRET:
        # Secret not configured — fail closed
        return False

    digest = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode()
    return hmac.compare_digest(computed, hmac_header)


def handle_payment_event(topic: str, payload: dict) -> None:
    
    source_identifier = payload.get("sourceIdentifier") or payload.get("source_identifier")
    if not source_identifier:
        return

    new_status = _TOPIC_STATUS.get(topic)
    if new_status is not None:
        update_status(source_identifier, new_status)
