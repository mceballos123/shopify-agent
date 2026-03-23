"""
Composio-powered Shopify OAuth connection manager.
Manages per-user Shopify authentication via Composio's connected_accounts API.
Each user (identified by their ASI1 sender address) gets their own connection.
"""

import os
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from composio import Composio
from dotenv import load_dotenv
from uagents import Context

from models import ShopifyRequest, ShopifyResponse

load_dotenv()

composio_client = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))


class ShopifyConnection:
    """Manages a single user's Shopify OAuth connection via Composio."""

    def __init__(self, user_id: str, auth_config_id: str | None = None):
        self.user_id = user_id
        self.auth_config_id = auth_config_id or os.getenv("SHOPIFY_AUTH_CONFIG_ID", "")
        self.composio = composio_client
        self.connected_account = None
        self.connection_request = None
        self.tools = None

    def initiate_auth(self) -> str:
        """Start Shopify OAuth flow via Composio.

        Returns:
            The redirect URL the user should visit to authorize Shopify access.

        Raises:
            RuntimeError: If the Composio initiate call fails.
        """
        try:
            self.connection_request = self.composio.connected_accounts.initiate(
                user_id=self.user_id,
                auth_config_id=self.auth_config_id,
            )
            return self.connection_request.redirect_url
        except Exception as exc:
            raise RuntimeError(f"Failed to initiate Shopify auth: {exc}") from exc

    def complete_auth(self, timeout: int = 30) -> bool:
        """Wait for the user to finish the OAuth flow.

        Args:
            timeout: Seconds to wait before giving up.

        Returns:
            True if the connection was established, False otherwise.
        """
        if not self.connection_request:
            return False
        try:
            self.connected_account = self.connection_request.wait_for_connection(
                timeout=timeout,
            )
            self.tools = self.composio.tools.get(
                user_id=self.user_id,
                toolkits=["SHOPIFY"],
            )
            return True
        except Exception:
            return False

    def is_authenticated(self) -> bool:
        """Check whether the user has an active Shopify connection."""
        return self.connected_account is not None and self.tools is not None

    def get_tools(self) -> Optional[list]:
        """Return Composio tool definitions for Shopify, or None if not authed."""
        return self.tools


# ── Per-user connection store ──────────────────────────────────────────────

_connections: dict[str, ShopifyConnection] = {}


def get_or_create_connection(user_id: str) -> ShopifyConnection:
    """Return the existing connection for *user_id*, or create a new one."""
    if user_id not in _connections:
        _connections[user_id] = ShopifyConnection(user_id=user_id)
    return _connections[user_id]


def get_connection(user_id: str) -> Optional[ShopifyConnection]:
    """Return the connection for *user_id* if it exists, else None."""
    return _connections.get(user_id)


# ── uAgent auth handlers ──────────────────────────────────────────────────

async def handle_connect_shopify(ctx: Context, sender: str, msg: ShopifyRequest):
    """Initiate Shopify OAuth — returns a redirect URL for the user."""
    conn = get_or_create_connection(sender)
    if conn.is_authenticated():
        await ctx.send(sender, ShopifyResponse(
            success=True,
            action="connect_shopify",
            data={"message": "Already connected to Shopify."},
        ))
        return
    try:
        redirect_url = conn.initiate_auth()
        ctx.logger.info(f"Shopify auth initiated for {sender}: {redirect_url}")
        await ctx.send(sender, ShopifyResponse(
            success=True,
            action="connect_shopify",
            redirect_url=redirect_url,
            data={"message": "Visit the URL to connect your Shopify account."},
        ))
    except RuntimeError as exc:
        ctx.logger.error(f"connect_shopify failed: {exc}")
        await ctx.send(sender, ShopifyResponse(
            success=False, action="connect_shopify", error=str(exc),
        ))


async def handle_complete_auth(ctx: Context, sender: str, msg: ShopifyRequest):
    """Poll Composio to see if the user finished OAuth."""
    conn = get_connection(sender)
    if not conn:
        await ctx.send(sender, ShopifyResponse(
            success=False,
            action="complete_auth",
            error="No pending connection. Send 'connect_shopify' first.",
        ))
        return
    if conn.is_authenticated():
        await ctx.send(sender, ShopifyResponse(
            success=True,
            action="complete_auth",
            data={"message": "Already authenticated."},
        ))
        return
    if conn.complete_auth():
        await ctx.send(sender, ShopifyResponse(
            success=True,
            action="complete_auth",
            data={"message": "Shopify account connected successfully!"},
        ))
    else:
        await ctx.send(sender, ShopifyResponse(
            success=False,
            action="complete_auth",
            error="Authentication not completed yet. Please finish the OAuth flow and try again.",
        ))


async def handle_check_connection(ctx: Context, sender: str, msg: ShopifyRequest):
    """Check whether the sender has an active Shopify connection."""
    conn = get_connection(sender)
    connected = conn.is_authenticated() if conn else False
    await ctx.send(sender, ShopifyResponse(
        success=True,
        action="check_connection",
        data={"connected": connected},
    ))
