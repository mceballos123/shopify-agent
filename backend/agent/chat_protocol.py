"""
Shopify chat protocol — message models and handlers.

Defines a Protocol that lets other agents interact with the Shopify
payment system through simple request/response messages.

Supported actions:
  - "create_session"  → create or resume a Shop Pay payment session
  - "session_status"  → look up the status of an existing session
  - "submit_payment"  → submit/confirm a payment for a session
"""

import sys
import os

# Ensure the backend package root is importable when running the agent
# script directly (e.g. `python agent/shopify_agent.py`).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from uagents import Context, Model, Protocol

from payments.session import get_or_create_payment_session, submit_payment
from payments.store import get_session
from payments.client import ShopPayAPIError


# ── Message models ───────────────────────────────────────────────────────────

class ShopifyRequest(Model):
    """Inbound request from another agent."""
    action: str          # "create_session" | "session_status" | "submit_payment"
    email: str = ""
    source_identifier: str = ""
    session_token: str = ""
    idempotency_key: str = ""
    line_items: list = []  # list of dicts: {label, quantity, price, sku?}


class ShopifyResponse(Model):
    """Outbound response back to the requesting agent."""
    success: bool
    action: str
    data: dict = {}
    error: str = ""


# ── Protocol definition ─────────────────────────────────────────────────────

shopify_protocol = Protocol(
    name="ShopifyPaymentProtocol",
    version="0.1.0",
)

DEFAULT_LINE_ITEMS = [
    {"label": "AI Agent Monthly Plan", "quantity": 1, "price": "29.99", "sku": "AGENT-001"},
]


@shopify_protocol.on_message(ShopifyRequest, replies=ShopifyResponse)
async def handle_shopify_request(ctx: Context, sender: str, msg: ShopifyRequest):
    """Route inbound requests to the appropriate payment handler."""
    ctx.logger.info(f"Received '{msg.action}' request from {sender}")

    if msg.action == "create_session":
        await _handle_create_session(ctx, sender, msg)
    elif msg.action == "session_status":
        await _handle_session_status(ctx, sender, msg)
    elif msg.action == "submit_payment":
        await _handle_submit_payment(ctx, sender, msg)
    else:
        await ctx.send(sender, ShopifyResponse(
            success=False,
            action=msg.action,
            error=f"Unknown action: {msg.action!r}. "
                  "Supported: create_session, session_status, submit_payment",
        ))


# ── Action handlers ──────────────────────────────────────────────────────────

async def _handle_create_session(ctx: Context, sender: str, msg: ShopifyRequest):
    """Create or resume a Shop Pay payment session."""
    line_items = msg.line_items or DEFAULT_LINE_ITEMS

    try:
        session = get_or_create_payment_session(
            line_items,
            source_identifier=msg.source_identifier or None,
        )
        await ctx.send(sender, ShopifyResponse(
            success=True,
            action="create_session",
            data={
                "checkout_url": session["checkout_url"],
                "source_identifier": session["source_identifier"],
                "token": session["token"],
            },
        ))
    except ShopPayAPIError as exc:
        ctx.logger.error(f"create_session failed: {exc}")
        await ctx.send(sender, ShopifyResponse(
            success=False,
            action="create_session",
            error=str(exc),
        ))


async def _handle_session_status(ctx: Context, sender: str, msg: ShopifyRequest):
    """Look up the current status of a payment session."""
    if not msg.source_identifier:
        await ctx.send(sender, ShopifyResponse(
            success=False,
            action="session_status",
            error="source_identifier is required",
        ))
        return

    record = get_session(msg.source_identifier)
    if record is None:
        await ctx.send(sender, ShopifyResponse(
            success=False,
            action="session_status",
            error=f"No session found for {msg.source_identifier!r}",
        ))
        return

    await ctx.send(sender, ShopifyResponse(
        success=True,
        action="session_status",
        data={
            "source_identifier": record.source_identifier,
            "status": record.status.value,
            "checkout_url": record.checkout_url,
            "token": record.token,
        },
    ))


async def _handle_submit_payment(ctx: Context, sender: str, msg: ShopifyRequest):
    """Submit/confirm a Shop Pay payment."""
    if not msg.session_token:
        await ctx.send(sender, ShopifyResponse(
            success=False,
            action="submit_payment",
            error="session_token is required",
        ))
        return

    line_items = msg.line_items or DEFAULT_LINE_ITEMS

    try:
        receipt = submit_payment(
            session_token=msg.session_token,
            line_items=line_items,
            idempotency_key=msg.idempotency_key or None,
        )
        await ctx.send(sender, ShopifyResponse(
            success=True,
            action="submit_payment",
            data=receipt,
        ))
    except ShopPayAPIError as exc:
        ctx.logger.error(f"submit_payment failed: {exc}")
        await ctx.send(sender, ShopifyResponse(
            success=False,
            action="submit_payment",
            error=str(exc),
        ))
