"""
Composio-powered Shopify OAuth connection manager.

Manages per-user Shopify authentication via Composio's connected_accounts API.
Each user (identified by their ASI1 sender address) gets their own connection.

Usage:
    conn = ShopifyConnection(user_id="user123", auth_config_id="cfg_xxx")
    url = conn.initiate_auth()        # returns redirect URL for user
    ok  = conn.complete_auth()         # polls until OAuth completes
    conn.is_authenticated()            # True once connected
    tools = conn.get_tools()           # Composio tool definitions for SHOPIFY
"""

import os
from typing import Optional

from composio import Composio
from dotenv import load_dotenv

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
