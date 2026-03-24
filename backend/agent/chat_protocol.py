"""
ASI1 Chat protocol for the Shopify Cart Agent.

Handles natural-language messages from ASI1 users via the standard chat
protocol. Routes through Gemini + Composio Shopify tools after ensuring
the user has authenticated via OAuth.

Flow:
  1. User sends a ChatMessage from ASI1
  2. Agent checks Composio OAuth status for the sender
  3. If not connected → initiates OAuth, returns auth link
  4. If connected → passes message to Gemini (llm_handler) which
     dynamically calls Composio Shopify tools as needed
  5. Returns Gemini's response as a ChatMessage
"""

import sys
import os
from datetime import datetime, timezone
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

from composio_auth.shopify_connection import get_or_create_connection, get_connection
from agent.llm_handler import process_message

chat_protocol = Protocol(spec=chat_protocol_spec)


@chat_protocol.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle an incoming chat message from ASI1."""
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    # Extract text content
    text = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text

    if not text.strip():
        await _reply(ctx, sender, "Please send a text message.")
        return

    ctx.logger.info(f"Chat from {sender}: {text[:80]}")

    # ── OAuth gate ──────────────────────────────────────────────────────
    conn = get_connection(sender)

    # If there's a pending connection request, try to complete it
    if conn and conn.connection_request and not conn.is_authenticated():
        if conn.complete_auth(timeout=5):
            ctx.logger.info(f"OAuth completed for {sender}")
        else:
            await _reply(
                ctx,
                sender,
                "Your Shopify authentication is still pending. "
                "Please complete the OAuth flow at the link I sent earlier, "
                "then send your message again.",
            )
            return

    # If no connection at all, initiate OAuth
    if not conn or not conn.is_authenticated():
        conn = get_or_create_connection(sender)
        try:
            redirect_url = conn.initiate_auth()
            await _reply(
                ctx,
                sender,
                f"You need to connect your Shopify account first.\n\n"
                f"Please visit this link to authorize:\n{redirect_url}\n\n"
                f"Once done, send your message again.",
            )
        except RuntimeError as exc:
            await _reply(
                ctx, sender, f"Failed to start Shopify authentication: {exc}"
            )
        return

    # ── Process via Gemini + Composio tools ──────────────────────────────
    try:
        response_text = await process_message(sender, text, conn)
        await _reply(ctx, sender, response_text)
    except Exception as exc:
        ctx.logger.error(f"LLM processing failed for {sender}: {exc}")
        await _reply(
            ctx, sender, f"Something went wrong processing your request: {exc}"
        )


@chat_protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


async def _reply(ctx: Context, sender: str, text: str):
    """Send a text reply back to the sender."""
    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=text)],
        ),
    )
