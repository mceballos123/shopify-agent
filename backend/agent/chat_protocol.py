"""
Shopify Cart protocol — message models and handlers.

Defines a Protocol that lets other agents interact with the Shopify
Storefront Cart API through simple request/response messages.

Supported actions:
  - "create_cart"           → create a new cart with line items
  - "add_lines"             → add merchandise lines to an existing cart
  - "update_lines"          → update quantities/variants on existing lines
  - "remove_lines"          → remove lines from a cart
  - "update_buyer_identity" → set buyer email/phone/country on a cart
  - "update_attributes"     → set custom key-value attributes on a cart
  - "get_cart"              → fetch current cart state
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from uagents import Context, Model, Protocol

from payments.cart import (
    create_cart,
    add_lines,
    update_lines,
    remove_lines,
    update_buyer_identity,
    update_attributes,
    get_cart,
)
from payments.client import StorefrontAPIError


# ── Message models ───────────────────────────────────────────────────────────

class ShopifyRequest(Model):
    """Inbound request from another agent."""
    action: str
    cart_id: str = ""
    lines: list = []
    line_ids: list = []
    buyer_identity: dict = {}
    attributes: list = []
    note: str = ""


class ShopifyResponse(Model):
    """Outbound response back to the requesting agent."""
    success: bool
    action: str
    data: dict = {}
    error: str = ""


# ── Protocol definition ─────────────────────────────────────────────────────

shopify_protocol = Protocol(
    name="ShopifyCartProtocol",
    version="0.2.0",
)

SUPPORTED_ACTIONS = [
    "create_cart", "add_lines", "update_lines", "remove_lines",
    "update_buyer_identity", "update_attributes", "get_cart",
]


@shopify_protocol.on_message(ShopifyRequest, replies=ShopifyResponse)
async def handle_shopify_request(ctx: Context, sender: str, msg: ShopifyRequest):
    """Route inbound requests to the appropriate cart handler."""
    ctx.logger.info(f"Received '{msg.action}' request from {sender}")

    handler = _HANDLERS.get(msg.action)
    if handler:
        await handler(ctx, sender, msg)
    else:
        await ctx.send(sender, ShopifyResponse(
            success=False,
            action=msg.action,
            error=f"Unknown action: {msg.action!r}. Supported: {', '.join(SUPPORTED_ACTIONS)}",
        ))


# ── Action handlers ──────────────────────────────────────────────────────────

async def _handle_create_cart(ctx: Context, sender: str, msg: ShopifyRequest):
    try:
        cart = create_cart(
            lines=msg.lines,
            buyer_identity=msg.buyer_identity or None,
            attributes=msg.attributes or None,
            note=msg.note or None,
        )
        await ctx.send(sender, ShopifyResponse(
            success=True, action="create_cart", data=cart,
        ))
    except StorefrontAPIError as exc:
        ctx.logger.error(f"create_cart failed: {exc}")
        await ctx.send(sender, ShopifyResponse(
            success=False, action="create_cart", error=str(exc),
        ))


async def _handle_add_lines(ctx: Context, sender: str, msg: ShopifyRequest):
    if not msg.cart_id:
        await ctx.send(sender, ShopifyResponse(
            success=False, action="add_lines", error="cart_id is required",
        ))
        return
    try:
        cart = add_lines(msg.cart_id, msg.lines)
        await ctx.send(sender, ShopifyResponse(
            success=True, action="add_lines", data=cart,
        ))
    except StorefrontAPIError as exc:
        ctx.logger.error(f"add_lines failed: {exc}")
        await ctx.send(sender, ShopifyResponse(
            success=False, action="add_lines", error=str(exc),
        ))


async def _handle_update_lines(ctx: Context, sender: str, msg: ShopifyRequest):
    if not msg.cart_id:
        await ctx.send(sender, ShopifyResponse(
            success=False, action="update_lines", error="cart_id is required",
        ))
        return
    try:
        cart = update_lines(msg.cart_id, msg.lines)
        await ctx.send(sender, ShopifyResponse(
            success=True, action="update_lines", data=cart,
        ))
    except StorefrontAPIError as exc:
        ctx.logger.error(f"update_lines failed: {exc}")
        await ctx.send(sender, ShopifyResponse(
            success=False, action="update_lines", error=str(exc),
        ))


async def _handle_remove_lines(ctx: Context, sender: str, msg: ShopifyRequest):
    if not msg.cart_id:
        await ctx.send(sender, ShopifyResponse(
            success=False, action="remove_lines", error="cart_id is required",
        ))
        return
    try:
        cart = remove_lines(msg.cart_id, msg.line_ids)
        await ctx.send(sender, ShopifyResponse(
            success=True, action="remove_lines", data=cart,
        ))
    except StorefrontAPIError as exc:
        ctx.logger.error(f"remove_lines failed: {exc}")
        await ctx.send(sender, ShopifyResponse(
            success=False, action="remove_lines", error=str(exc),
        ))


async def _handle_update_buyer_identity(ctx: Context, sender: str, msg: ShopifyRequest):
    if not msg.cart_id:
        await ctx.send(sender, ShopifyResponse(
            success=False, action="update_buyer_identity", error="cart_id is required",
        ))
        return
    try:
        cart = update_buyer_identity(msg.cart_id, msg.buyer_identity)
        await ctx.send(sender, ShopifyResponse(
            success=True, action="update_buyer_identity", data=cart,
        ))
    except StorefrontAPIError as exc:
        ctx.logger.error(f"update_buyer_identity failed: {exc}")
        await ctx.send(sender, ShopifyResponse(
            success=False, action="update_buyer_identity", error=str(exc),
        ))


async def _handle_update_attributes(ctx: Context, sender: str, msg: ShopifyRequest):
    if not msg.cart_id:
        await ctx.send(sender, ShopifyResponse(
            success=False, action="update_attributes", error="cart_id is required",
        ))
        return
    try:
        cart = update_attributes(msg.cart_id, msg.attributes)
        await ctx.send(sender, ShopifyResponse(
            success=True, action="update_attributes", data=cart,
        ))
    except StorefrontAPIError as exc:
        ctx.logger.error(f"update_attributes failed: {exc}")
        await ctx.send(sender, ShopifyResponse(
            success=False, action="update_attributes", error=str(exc),
        ))


async def _handle_get_cart(ctx: Context, sender: str, msg: ShopifyRequest):
    if not msg.cart_id:
        await ctx.send(sender, ShopifyResponse(
            success=False, action="get_cart", error="cart_id is required",
        ))
        return
    try:
        cart = get_cart(msg.cart_id)
        await ctx.send(sender, ShopifyResponse(
            success=True, action="get_cart", data=cart,
        ))
    except StorefrontAPIError as exc:
        ctx.logger.error(f"get_cart failed: {exc}")
        await ctx.send(sender, ShopifyResponse(
            success=False, action="get_cart", error=str(exc),
        ))


_HANDLERS = {
    "create_cart": _handle_create_cart,
    "add_lines": _handle_add_lines,
    "update_lines": _handle_update_lines,
    "remove_lines": _handle_remove_lines,
    "update_buyer_identity": _handle_update_buyer_identity,
    "update_attributes": _handle_update_attributes,
    "get_cart": _handle_get_cart,
}
