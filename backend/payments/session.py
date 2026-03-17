from .client import execute_graphql, ShopPayAPIError
from .builder import build_payment_request
from .idempotency import generate_idempotency_key, generate_source_identifier
from .store import PaymentRecord, PaymentStatus, get_session, save_session
from graphql.mutations import SESSION_CREATE_MUTATION, SESSION_SUBMIT_MUTATION


def create_payment_session(
    line_items: list[dict],
    source_identifier: str | None = None,
    **kwargs,
) -> dict:
    """
    Create a Shop Pay payment request session and persist it in the store.

    Returns the session token, checkout URL, source identifier, and the
    idempotency key bound to this session.
    """
    if source_identifier is None:
        source_identifier = generate_source_identifier()

    idempotency_key = generate_idempotency_key()
    payment_request = build_payment_request(line_items, **kwargs)

    result = execute_graphql(SESSION_CREATE_MUTATION, {
        "sourceIdentifier": source_identifier,
        "paymentRequest": payment_request,
    })

    session_data = result["shopPayPaymentRequestSessionCreate"]

    if session_data["userErrors"]:
        raise ShopPayAPIError(
            f"Session create errors: {session_data['userErrors']}"
        )

    session = session_data["shopPayPaymentRequestSession"]

    record = PaymentRecord(
        source_identifier=session["sourceIdentifier"],
        idempotency_key=idempotency_key,
        checkout_url=session["checkoutUrl"],
        token=session["token"],
    )
    save_session(record)

    return {
        "token": record.token,
        "checkout_url": record.checkout_url,
        "source_identifier": record.source_identifier,
        "idempotency_key": record.idempotency_key,
        "payment_request": session["paymentRequest"],
    }


def get_or_create_payment_session(
    line_items: list[dict],
    source_identifier: str | None = None,
    **kwargs,
) -> dict:
    """
    Return an existing PENDING session if one exists for source_identifier,
    otherwise create a new one.

    This is the safe entry point to call on every checkout page load,
    including page refreshes. Shopify webhooks update the stored status
    when a payment resolves or is rejected, so a completed or failed session
    will never be reused as an active session.

    Raises ShopPayAPIError if the session has already completed or failed.
    """
    if source_identifier:
        record = get_session(source_identifier)
        if record is not None:
            if record.status == PaymentStatus.COMPLETED:
                raise ShopPayAPIError(
                    f"Payment for session {source_identifier!r} already completed."
                )
            if record.status == PaymentStatus.FAILED:
                raise ShopPayAPIError(
                    f"Payment for session {source_identifier!r} previously failed. "
                    "Start a new checkout to retry."
                )
            # PENDING — return the existing session so no new charge is initiated
            return {
                "token": record.token,
                "checkout_url": record.checkout_url,
                "source_identifier": record.source_identifier,
                "idempotency_key": record.idempotency_key,
            }

    return create_payment_session(line_items, source_identifier=source_identifier, **kwargs)


def submit_payment(
    session_token: str,
    line_items: list[dict],
    idempotency_key: str | None = None,
    order_name: str | None = None,
    **kwargs,
) -> dict:
    """
    Submit (confirm) a Shop Pay payment. Uses an idempotency key to
    guarantee the charge is processed exactly once.

    Prefer passing the idempotency_key retrieved from create_payment_session
    so retries are safe. If omitted, a new key is generated.
    """
    if idempotency_key is None:
        idempotency_key = generate_idempotency_key()

    payment_request = build_payment_request(line_items, **kwargs)

    variables = {
        "token": session_token,
        "paymentRequest": payment_request,
        "idempotencyKey": idempotency_key,
    }
    if order_name:
        variables["orderName"] = order_name

    result = execute_graphql(SESSION_SUBMIT_MUTATION, variables)

    submit_data = result["shopPayPaymentRequestSessionSubmit"]

    if submit_data["userErrors"]:
        raise ShopPayAPIError(
            f"Payment submit errors: {submit_data['userErrors']}"
        )

    receipt = submit_data["paymentRequestReceipt"]
    return {
        "receipt_token": receipt["token"],
        "processing_status": receipt["processingStatusType"],
        "idempotency_key": idempotency_key,
    }
