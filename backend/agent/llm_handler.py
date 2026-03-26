"""
OpenAI LLM handler with Storefront tools and stateful sessions.

Manages per-user conversation history and processes natural-language
messages through OpenAI, which can call Storefront tools (browse products,
manage cart, get checkout URL) via graphql/tools.py.
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

from graphql.declarations import TOOL_DECLARATIONS as STOREFRONT_TOOLS
from graphql.tools import TOOL_EXECUTORS

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

SHOPIFY_PROMPT = """
You are a Shopify shopping assistant agent powered by Fetch.ai.

You help users browse the store's products, add items to a cart, and
check out. No login is needed to browse or build a cart — Shopify
handles payment and authentication at checkout time.

What you can do:
- Show the store's products when the user wants to browse (use get_products)
- Create a cart and add items for the user (use create_cart)
- Add, update, or remove items from their cart (use add_lines, update_lines, remove_lines)
- Set buyer identity on the cart (use update_buyer_identity)
- Fetch current cart state (use get_cart)

When the user is done shopping, provide them with the checkout URL from the
cart response — they will sign in and complete payment on Shopify's checkout page.

Be concise and helpful. If a tool call fails, explain the error clearly.
Always confirm what you did after each action.
"""


# ── Per-user session store (stateful across refreshes) ─────────────────────

_sessions: dict[str, list] = {}


def get_history(user_id: str) -> list:
    """Return stored conversation history for a user."""
    return _sessions.get(user_id, [])


def clear_history(user_id: str) -> None:
    """Clear a user's conversation history."""
    _sessions.pop(user_id, None)


# ── Build OpenAI tools from Storefront declarations ───────────────────────

def _build_openai_tools() -> list:
    """Convert storefront tool declarations into OpenAI function-calling format."""
    tools = []
    for decl in STOREFRONT_TOOLS:
        tools.append({
            "type": "function",
            "function": {
                "name": decl["name"],
                "description": decl.get("description", ""),
                "parameters": decl.get("parameters", {"type": "object", "properties": {}}),
            },
        })
    return tools


_OPENAI_TOOLS = _build_openai_tools()


# ── Tool execution ────────────────────────────────────────────────────────

def _execute_tool(name: str, args: dict) -> dict:
    """Execute a Storefront tool call."""
    if name in TOOL_EXECUTORS:
        try:
            result = TOOL_EXECUTORS[name](**args)
            return {"success": True, "data": result}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    return {"success": False, "error": f"Unknown tool: {name}"}


# ── Main message processing ───────────────────────────────────────────────

async def process_message(user_id: str, text: str) -> str:
    """Send a user message through OpenAI with Storefront tools.

    Args:
        user_id: The sender's identifier (used for session tracking).
        text: The user's natural-language message.

    Returns:
        The assistant's text response.
    """
    history = get_history(user_id)

    messages = [{"role": "system", "content": SHOPIFY_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": text})

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=_OPENAI_TOOLS if _OPENAI_TOOLS else None,
        )

        choice = response.choices[0]
        assistant_message = choice.message

        messages.append(assistant_message.model_dump(exclude_none=True))

        if not assistant_message.tool_calls:
            break

        for tool_call in assistant_message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

            result = _execute_tool(name, args)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

    _sessions[user_id] = messages[1:]

    return assistant_message.content or ""
