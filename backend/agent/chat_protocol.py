"""
ASI1 Chat protocol for the Shopify Cart Agent.

Handles natural-language messages from ASI1 users via the standard chat
protocol. Routes through OpenAI + Storefront API tools to browse products,
manage a cart, and provide a checkout URL.

Flow:
  1. User sends a ChatMessage from ASI1
  2. Agent passes message to OpenAI (llm_handler) which calls
     Storefront tools (products, cart, checkout) as needed
  3. Returns OpenAI's response as a ChatMessage
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

    text = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text

    if not text.strip():
        await _reply(ctx, sender, "Please send a text message.")
        return

    ctx.logger.info(f"Chat from {sender}: {text[:80]}")

    try:
        response_text = await process_message(sender, text)
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
