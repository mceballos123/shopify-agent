
from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from payments.auth import get_frontend_config
from payments.callback import handle_payment_callback
from payments.client import ShopPayAPIError
from payments.session import get_or_create_payment_session, submit_payment
from payments.store import get_session
from webhooks.handler import handle_payment_event, verify_webhook

app = FastAPI(title="Shop Pay Integration")

templates = Jinja2Templates(directory="templates")


# ── Request / Response models ───────────────────────────────────────────────

class SessionRequest(BaseModel):
    email: str
    line_items: list[dict] | None = None
    # Sent by the client on page refresh to resume an existing session
    source_identifier: str | None = None


class SubmitRequest(BaseModel):
    session_token: str
    line_items: list[dict] | None = None
    idempotency_key: str | None = None


# ── Routes ───────────────────────────────────────────────────────────────────

# Serve the checkout UI with Shop Pay SDK config injected.
# Watches the email field and triggers the Shop Pay auth modal automatically.
@app.get("/checkout")
def checkout_page(request: Request):
    config = get_frontend_config()
    return templates.TemplateResponse(
        "checkout.html",
        {"request": request, **config},
    )


# Create or resume a Shop Pay session. Client stores source_identifier in
# localStorage and sends it back on refresh to avoid duplicate charges.
@app.post("/api/payment/session")
def create_session(body: SessionRequest):
    default_items = [
        {"label": "AI Agent Monthly Plan", "quantity": 1, "price": "29.99", "sku": "AGENT-001"},
    ]
    line_items = body.line_items or default_items

    try:
        session = get_or_create_payment_session(
            line_items,
            source_identifier=body.source_identifier,
        )
        return JSONResponse({
            "checkout_url": session["checkout_url"],
            "source_identifier": session["source_identifier"],
            "token": session["token"],
        })
    except ShopPayAPIError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=502)


# Receive signed Shopify webhook events for payment_sessions/resolve|reject.
# Verifies HMAC-SHA256 signature before updating session state.
@app.post("/webhooks/payment")
async def payment_webhook(
    request: Request,
    x_shopify_hmac_sha256: str = Header(default=""),
    x_shopify_topic: str = Header(default=""),
):
    body = await request.body()

    if not verify_webhook(body, x_shopify_hmac_sha256):
        return JSONResponse({"detail": "Invalid webhook signature"}, status_code=401)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid JSON payload"}, status_code=400)

    handle_payment_event(x_shopify_topic, payload)
    return JSONResponse({"received": True})


# Post-payment redirect target. Verifies receipt via source_identifier and
# redirects the user to the appropriate dashboard page based on payment status.
@app.get("/payment/callback")
def payment_callback(
    source_identifier: str = Query(default="", alias="source_identifier"),
):
    redirect_url, status_code = handle_payment_callback(source_identifier)
    return RedirectResponse(url=redirect_url, status_code=status_code)


# Serve the test dashboard UI for exercising all agent endpoints.
@app.get("/test")
def test_dashboard(request: Request):
    return templates.TemplateResponse("test_dashboard.html", {"request": request})


# Look up the current status of a payment session by source_identifier.
@app.get("/api/session/status")
def session_status(source_identifier: str = Query(...)):
    record = get_session(source_identifier)
    if record is None:
        return JSONResponse(
            {"detail": f"No session found for {source_identifier!r}"},
            status_code=404,
        )
    return JSONResponse({
        "source_identifier": record.source_identifier,
        "status": record.status.value,
        "checkout_url": record.checkout_url,
        "token": record.token,
    })


# Submit/confirm a Shop Pay payment.
@app.post("/api/payment/submit")
def submit_payment_endpoint(body: SubmitRequest):
    default_items = [
        {"label": "AI Agent Monthly Plan", "quantity": 1, "price": "29.99", "sku": "AGENT-001"},
    ]
    line_items = body.line_items or default_items

    try:
        receipt = submit_payment(
            session_token=body.session_token,
            line_items=line_items,
            idempotency_key=body.idempotency_key,
        )
        return JSONResponse(receipt)
    except ShopPayAPIError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=502)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    # Development only — use `uvicorn server:app` directly in production
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
