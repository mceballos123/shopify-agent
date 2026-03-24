"""
HTTP session manager for OAuth state and conversation persistence.

Tracks per-session Shopify OAuth connections and ties them to the
Gemini conversation history in llm_handler. Sessions are identified
by a cookie-based session ID so state survives page refreshes.

This file is separate from shopify_agent.py because it handles
HTTP/FastAPI concerns, not uAgent protocol setup.
"""

import secrets
from typing import Optional

from fastapi import Request, Response

from composio_auth.shopify_connection import (
    ShopifyConnection,
    get_or_create_connection,
    get_connection,
)


SESSION_COOKIE = "shopify_session_id"


def _get_or_set_session_id(request: Request, response: Response) -> str:
    """Return the session ID from the cookie, or generate and set a new one."""
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        session_id = secrets.token_urlsafe(32)
        response.set_cookie(
            SESSION_COOKIE,
            session_id,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 7,  # 1 week
        )
    return session_id


def get_session_connection(session_id: str) -> Optional[ShopifyConnection]:
    """Return the OAuth connection for this session, or None."""
    return get_connection(session_id)


def ensure_authenticated(session_id: str) -> tuple[bool, Optional[ShopifyConnection], Optional[str]]:
    """Check OAuth status for a session.

    Returns:
        (is_authed, connection, message)
        - If authed: (True, connection, None)
        - If pending: (False, connection, instructions)
        - If no connection: (False, None, None) — caller should initiate
    """
    conn = get_connection(session_id)

    if conn and conn.connection_request and not conn.is_authenticated():
        if conn.complete_auth(timeout=5):
            return True, conn, None
        return False, conn, (
            "Your Shopify authentication is still pending. "
            "Please complete the OAuth flow at the link provided, "
            "then try again."
        )

    if conn and conn.is_authenticated():
        return True, conn, None

    return False, None, None


def initiate_session_auth(session_id: str) -> str:
    """Start OAuth for a session. Returns the redirect URL."""
    conn = get_or_create_connection(session_id)
    return conn.initiate_auth()
