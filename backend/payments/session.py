from .client import execute_graphql, ShopPayAPIError
from .builder import build_payment_request
from .idempotency import generate_idempotency_key, generate_source_identifier
from graphql.mutations import SESSION_CREATE_MUTATION, SESSION_SUBMIT_MUTATION


def create_payment_session(
    line_items: list[dict],
    source_identifier: str | None = None,
    **kwargs,
) -> dict:
    """
    Create a Shop Pay payment request session.

    Returns the session token, checkout URL, and source identifier needed
    for subsequent operations.
    """
    if source_identifier is None:
        source_identifier = generate_source_identifier()

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
    return {
        "token": session["token"],
        "checkout_url": session["checkoutUrl"],
        "source_identifier": session["sourceIdentifier"],
        "payment_request": session["paymentRequest"],
    }


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

    If no idempotency_key is provided, one is generated automatically.
    Store the key if you need to safely retry.
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
