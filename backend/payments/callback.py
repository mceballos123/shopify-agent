import os
from .client import execute_graphql, ShopPayAPIError
from graphql.queries import RECEIPT_LOOKUP_QUERY

# Placeholder — replace with your actual dashboard base URL
# or set DASHBOARD_BASE_URL in your .env file
DASHBOARD_BASE_URL = os.getenv("DASHBOARD_BASE_URL", "https://YOUR_DASHBOARD_URL")


def verify_payment_receipt(source_identifier: str) -> dict:
    """
    Look up a Shop Pay receipt by source identifier.

    Calls the shopPayPaymentRequestReceipts query and returns the first
    matching receipt, or raises ShopPayAPIError if none is found.
    """
    result = execute_graphql(
        RECEIPT_LOOKUP_QUERY,
        {"sourceIdentifier": source_identifier},
    )

    receipts = result.get("shopPayPaymentRequestReceipts", [])
    if not receipts:
        raise ShopPayAPIError(
            f"No receipt found for source_identifier={source_identifier!r}"
        )

    return receipts[0]


def build_redirect_url(source_identifier: str, receipt: dict) -> str:
    """
    Build the dashboard redirect URL based on payment outcome.

    - ready   → /orders/<source_identifier>?status=paid
    - pending → /orders/<source_identifier>?status=pending
    - other   → /checkout?error=payment_failed&ref=<source_identifier>
    """
    status = receipt.get("processingStatusType", "").lower()

    if status == "ready":
        return f"{DASHBOARD_BASE_URL}/orders/{source_identifier}?status=paid"
    elif status == "pending":
        return f"{DASHBOARD_BASE_URL}/orders/{source_identifier}?status=pending"
    else:
        return (
            f"{DASHBOARD_BASE_URL}/checkout"
            f"?error=payment_failed&ref={source_identifier}"
        )


def handle_payment_callback(source_identifier: str) -> tuple[str, int]:
    """
    Full callback handler: verify the receipt, then return the redirect URL
    and an appropriate HTTP status code.

    Returns:
        (redirect_url, http_status_code)
    """
    if not source_identifier:
        return f"{DASHBOARD_BASE_URL}/checkout?error=missing_reference", 302

    try:
        receipt = verify_payment_receipt(source_identifier)
        redirect_url = build_redirect_url(source_identifier, receipt)
        return redirect_url, 302
    except ShopPayAPIError as exc:
        print(f"[callback] ShopPayAPIError: {exc}")
        return (
            f"{DASHBOARD_BASE_URL}/checkout"
            f"?error=verification_failed&ref={source_identifier}",
            302,
        )
