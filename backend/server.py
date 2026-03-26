import secrets

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.llm_handler import process_message

app = FastAPI(title="Shopify Agent API")

SESSION_COOKIE = "shopify_session_id"


def _get_or_set_session_id(request: Request, response: JSONResponse) -> str:
    """Return the session ID from the cookie, or generate and set a new one."""
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        session_id = secrets.token_urlsafe(32)
        response.set_cookie(
            SESSION_COOKIE,
            session_id,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 7,
        )
    return session_id


class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
async def chat_endpoint(body: ChatRequest, request: Request):
    """Send a message to the Shopify shopping assistant."""
    response = JSONResponse({})
    session_id = _get_or_set_session_id(request, response)

    try:
        reply = await process_message(session_id, body.message)
        return JSONResponse({"reply": reply})
    except Exception as exc:
        return JSONResponse(
            {"detail": f"Something went wrong: {exc}"},
            status_code=500,
        )


@app.get("/health")
def health():
    return {"status": "ok"}
