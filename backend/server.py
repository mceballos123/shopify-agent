import os

from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from pydantic import BaseModel

from models import (
    CartCreateRequest,
    CartLinesAddRequest,
    CartLinesUpdateRequest,
    CartLinesRemoveRequest,
    CartBuyerIdentityRequest,
    CartAttributesRequest,
)
from payments.client import StorefrontAPIError
from agent.session_manager import (
    _get_or_set_session_id,
    ensure_authenticated,
    initiate_session_auth,
)
from agent.llm_handler import process_message
from payments.cart import (
    create_cart,
    add_lines,
    update_lines,
    remove_lines,
    update_buyer_identity,
    update_attributes,
    get_cart,
    get_products,
)
from payments.store import get_cart as get_cart_record
from webhooks.handler import (
    handle_order_creation,
    handle_order_cancellation,
    handle_order_payment,
    verify_webhook,
)

app = FastAPI(title="Shopify Storefront Cart API")

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(_BASE_DIR, "templates"))


# ── Cart Routes ──────────────────────────────────────────────────────────────

@app.post("/api/cart")
def create_cart_endpoint(body: CartCreateRequest):
    try:
        cart = create_cart(
            lines=[ln.model_dump() for ln in body.lines],
            buyer_identity=body.buyer_identity,
            attributes=body.attributes,
            note=body.note,
        )
        return JSONResponse(cart)
    except StorefrontAPIError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=502)


@app.get("/api/cart")
def get_cart_endpoint(cart_id: str = Query(...)):
    try:
        cart = get_cart(cart_id)
        return JSONResponse(cart)
    except StorefrontAPIError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=502)


@app.post("/api/cart/lines/add")
def add_lines_endpoint(body: CartLinesAddRequest):
    try:
        cart = add_lines(
            body.cart_id,
            [ln.model_dump() for ln in body.lines],
        )
        return JSONResponse(cart)
    except StorefrontAPIError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=502)


@app.post("/api/cart/lines/update")
def update_lines_endpoint(body: CartLinesUpdateRequest):
    try:
        cart = update_lines(
            body.cart_id,
            [ln.model_dump(exclude_none=True) for ln in body.lines],
        )
        return JSONResponse(cart)
    except StorefrontAPIError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=502)


@app.post("/api/cart/lines/remove")
def remove_lines_endpoint(body: CartLinesRemoveRequest):
    try:
        cart = remove_lines(body.cart_id, body.line_ids)
        return JSONResponse(cart)
    except StorefrontAPIError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=502)


@app.post("/api/cart/buyer-identity")
def update_buyer_identity_endpoint(body: CartBuyerIdentityRequest):
    try:
        cart = update_buyer_identity(body.cart_id, body.buyer_identity)
        return JSONResponse(cart)
    except StorefrontAPIError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=502)


@app.post("/api/cart/attributes")
def update_attributes_endpoint(body: CartAttributesRequest):
    try:
        cart = update_attributes(body.cart_id, body.attributes)
        return JSONResponse(cart)
    except StorefrontAPIError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=502)


# ── Products ─────────────────────────────────────────────────────────────────

@app.get("/api/products")
def list_products(
    first: int = Query(default=20, ge=1, le=50),
    after: str | None = Query(default=None),
):
    try:
        return JSONResponse(get_products(first=first, after=after))
    except StorefrontAPIError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=502)


# ── Cart status from local store ─────────────────────────────────────────────

@app.get("/api/cart/status")
def cart_status(cart_id: str = Query(...)):
    record = get_cart_record(cart_id)
    if record is None:
        return JSONResponse(
            {"detail": f"No cart record found for {cart_id!r}"},
            status_code=404,
        )
    return JSONResponse({
        "cart_id": record.cart_id,
        "status": record.status.value,
        "checkout_url": record.checkout_url,
        "order_id": record.order_id,
    })


# ── Order Webhooks ───────────────────────────────────────────────────────────

async def _parse_and_verify(request: Request, hmac_header: str) -> dict | None:
    """Shared helper: verify signature and parse JSON body."""
    body = await request.body()
    if not verify_webhook(body, hmac_header):
        return None
    return await request.json()


@app.post("/webhooks/order/payment")
async def order_payment_webhook(
    request: Request,
    x_shopify_hmac_sha256: str = Header(default=""),
):
    try:
        payload = await _parse_and_verify(request, x_shopify_hmac_sha256)
        if payload is None:
            return JSONResponse({"detail": "Invalid webhook signature"}, status_code=401)
        handle_order_payment(payload)
        return JSONResponse({"received": True})
    except Exception as exc:
        return JSONResponse({"detail": f"Payment webhook error: {exc}"}, status_code=500)


@app.post("/order/creation")
async def order_creation_webhook(
    request: Request,
    x_shopify_hmac_sha256: str = Header(default=""),
):
    try:
        payload = await _parse_and_verify(request, x_shopify_hmac_sha256)
        if payload is None:
            return JSONResponse({"detail": "Invalid webhook signature"}, status_code=401)
        handle_order_creation(payload)
        return JSONResponse({"received": True})
    except Exception as exc:
        return JSONResponse({"detail": f"Creation webhook error: {exc}"}, status_code=500)


@app.post("/order/cancellation")
async def order_cancellation_webhook(
    request: Request,
    x_shopify_hmac_sha256: str = Header(default=""),
):
    try:
        payload = await _parse_and_verify(request, x_shopify_hmac_sha256)
        if payload is None:
            return JSONResponse({"detail": "Invalid webhook signature"}, status_code=401)
        handle_order_cancellation(payload)
        return JSONResponse({"received": True})
    except Exception as exc:
        return JSONResponse({"detail": f"Cancellation webhook error: {exc}"}, status_code=500)


# ── OAuth + Chat (HTTP) ───────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str


@app.get("/api/auth/status")
def auth_status(request: Request):
    """Check whether the current session has a valid Shopify OAuth connection."""
    response = JSONResponse({"authenticated": False})
    session_id = _get_or_set_session_id(request, response)
    is_authed, _, msg = ensure_authenticated(session_id)
    if is_authed:
        return JSONResponse({"authenticated": True})
    if msg:
        return JSONResponse({"authenticated": False, "message": msg})
    return response


@app.post("/api/auth/initiate")
def auth_initiate(request: Request):
    """Start the Shopify OAuth flow and return the redirect URL."""
    response = JSONResponse({})
    session_id = _get_or_set_session_id(request, response)

    is_authed, _, _ = ensure_authenticated(session_id)
    if is_authed:
        return JSONResponse({"authenticated": True})

    try:
        redirect_url = initiate_session_auth(session_id)
        return JSONResponse({"redirect_url": redirect_url})
    except RuntimeError as exc:
        return JSONResponse(
            {"detail": f"Failed to start Shopify authentication: {exc}"},
            status_code=500,
        )


@app.post("/api/chat")
async def chat_endpoint(body: ChatRequest, request: Request):
    """Send a message to the Gemini-powered Shopify assistant.

    Requires an active OAuth session — returns 401 with instructions if not.
    """
    response = JSONResponse({})
    session_id = _get_or_set_session_id(request, response)

    is_authed, conn, msg = ensure_authenticated(session_id)
    if not is_authed:
        detail = msg or (
            "You need to connect your Shopify account first. "
            "Call POST /api/auth/initiate to get started."
        )
        return JSONResponse({"detail": detail}, status_code=401)

    try:
        reply = await process_message(session_id, body.message, conn)
        return JSONResponse({"reply": reply})
    except Exception as exc:
        return JSONResponse(
            {"detail": f"Something went wrong: {exc}"},
            status_code=500,
        )


# ── UI ───────────────────────────────────────────────────────────────────────

@app.get("/checkout")
def checkout_page(request: Request):
    store_domain = os.getenv("SHOPIFY_STORE_DOMAIN", "")
    return templates.TemplateResponse(
        "checkout.html",
        {"request": request, "store_domain": store_domain},
    )


@app.get("/test")
def test_dashboard(request: Request):
    return templates.TemplateResponse("test_dashboard.html", {"request": request})


@app.get("/health")
def health():
    return {"status": "ok"}
