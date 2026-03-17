
from fastapi import FastAPI, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from payments.auth import create_auth_session, get_frontend_config
from payments.callback import handle_payment_callback
from payments.client import ShopPayAPIError

app = FastAPI(title="Shop Pay Integration")

templates = Jinja2Templates(directory="templates")


# ── Request / Response models ───────────────────────────────────────────────

class SessionRequest(BaseModel):
    email: str
    line_items: list[dict] | None = None


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/checkout")
def checkout_page(request: Request):
    """
    Serve the company checkout UI.

    The page embeds the Shop Pay client SDK and calls
    ShopPay.PaymentRequest.createLogin({emailInputId: 'email-input'})
    to watch the email field. When a recognised Shop Pay email is typed,
    the authentication modal appears automatically, allowing the customer
    to authenticate via email, SMS, or passkey.
    """
    config = get_frontend_config()
    return templates.TemplateResponse(
        "checkout.html",
        {"request": request, **config},
    )


@app.post("/api/payment/session")
def create_session(body: SessionRequest):
    """
    Create a Shop Pay payment request session.

    Called by the checkout UI after the user enters their email (and
    optionally authenticates via Shop Pay). Returns the hosted
    checkout URL that the browser should redirect to.

    Body:
        email      – customer email (informational; Shop Pay owns auth)
        line_items – optional cart override; falls back to the default plan
    """
    default_items = [
        {"label": "AI Agent Monthly Plan", "quantity": 1, "price": "29.99", "sku": "AGENT-001"},
    ]
    line_items = body.line_items or default_items

    try:
        session = create_auth_session(line_items)
        return JSONResponse({
            "checkout_url": session["checkout_url"],
            "source_identifier": session["source_identifier"],
            "token": session["token"],
        })
    except ShopPayAPIError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=502)


@app.get("/payment/callback")
def payment_callback(
    source_identifier: str = Query(default="", alias="source_identifier"),
):
    """
    Shop Pay post-payment redirect target.

    Shopify appends the source_identifier that was passed to
    shopPayPaymentRequestSessionCreate, allowing us to look up the
    receipt and verify payment status before sending the user to the
    appropriate dashboard page.
    """
    redirect_url, status_code = handle_payment_callback(source_identifier)
    return RedirectResponse(url=redirect_url, status_code=status_code)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    # Development only — use `uvicorn server:app` directly in production
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
