import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from pydantic import BaseModel

from agent.session_manager import (
    _get_or_set_session_id,
    ensure_authenticated,
    initiate_session_auth,
)
from agent.llm_handler import process_message

app = FastAPI(title="Shopify Agent API")

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(_BASE_DIR, "templates"))


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
