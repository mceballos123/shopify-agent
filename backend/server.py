import os

from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from payments.client import StorefrontAPIError
from payments.cart import (
    create_cart,
    add_lines,
    update_lines,
    remove_lines,
    update_buyer_identity,
    update_attributes,
    get_cart,
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


# ── Request models ───────────────────────────────────────────────────────────

class CartLineInput(BaseModel):
    merchandise_id: str
    quantity: int = 1
    attributes: list[dict] | None = None


class CartCreateRequest(BaseModel):
    lines: list[CartLineInput]
    buyer_identity: dict | None = None
    attributes: list[dict] | None = None
    note: str | None = None


class CartLinesAddRequest(BaseModel):
    cart_id: str
    lines: list[CartLineInput]


class CartLineUpdateInput(BaseModel):
    id: str
    quantity: int | None = None
    merchandise_id: str | None = None
    attributes: list[dict] | None = None


class CartLinesUpdateRequest(BaseModel):
    cart_id: str
    lines: list[CartLineUpdateInput]


class CartLinesRemoveRequest(BaseModel):
    cart_id: str
    line_ids: list[str]


class CartBuyerIdentityRequest(BaseModel):
    cart_id: str
    buyer_identity: dict


class CartAttributesRequest(BaseModel):
    cart_id: str
    attributes: list[dict]


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
    payload = await _parse_and_verify(request, x_shopify_hmac_sha256)
    if payload is None:
        return JSONResponse({"detail": "Invalid webhook signature"}, status_code=401)
    handle_order_payment(payload)
    return JSONResponse({"received": True})


@app.post("/order/creation")
async def order_creation_webhook(
    request: Request,
    x_shopify_hmac_sha256: str = Header(default=""),
):
    payload = await _parse_and_verify(request, x_shopify_hmac_sha256)
    if payload is None:
        return JSONResponse({"detail": "Invalid webhook signature"}, status_code=401)
    handle_order_creation(payload)
    return JSONResponse({"received": True})


@app.post("/order/cancellation")
async def order_cancellation_webhook(
    request: Request,
    x_shopify_hmac_sha256: str = Header(default=""),
):
    payload = await _parse_and_verify(request, x_shopify_hmac_sha256)
    if payload is None:
        return JSONResponse({"detail": "Invalid webhook signature"}, status_code=401)
    handle_order_cancellation(payload)
    return JSONResponse({"received": True})


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
