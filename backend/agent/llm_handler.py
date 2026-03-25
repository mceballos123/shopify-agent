"""
OpenAI LLM handler with Storefront + Composio Shopify tools and stateful sessions.

Manages per-user conversation history and processes natural-language
messages through OpenAI, which can call:
  - Storefront tools (browse products, manage cart) via graphql/tools.py
  - Composio Shopify tools (OAuth-gated admin actions) dynamically
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

The user has logged into their Shopify account via OAuth. They are now
browsing your store's inventory and can manage their cart.

What you can do:
- Show the store's products when the user wants to browse (use get_products)
- Create a cart and add items for the user (use create_cart)
- Add, update, or remove items from their cart (use add_lines, update_lines, remove_lines)
- Set buyer identity on the cart (use update_buyer_identity)
- Fetch current cart state (use get_cart)

When the user is done shopping, provide them with the checkout URL from the
cart response — Shopify handles the payment from there.

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


# ── Tool merging: Storefront + Composio ───────────────────────────────────

def _build_openai_tools(composio_tools: list | None) -> list:
    """Merge storefront tool declarations with Composio tool declarations into OpenAI format."""
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

    if composio_tools:
        for tool in composio_tools:
            func = tool.get("function", tool)
            tools.append({
                "type": "function",
                "function": {
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {"type": "object", "properties": {}}),
                },
            })

    return tools


# ── Tool execution routing ────────────────────────────────────────────────

def _execute_tool(composio_client, user_id: str, name: str, args: dict) -> dict:
    """Execute a tool call — route to storefront or Composio."""
    # Storefront tools (our own GraphQL operations)
    if name in TOOL_EXECUTORS:
        try:
            result = TOOL_EXECUTORS[name](**args)
            return {"success": True, "data": result}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # Composio tools (dynamic Shopify admin actions)
    try:
        result = composio_client.actions.execute(
            action=name,
            params=args,
            entity_id=user_id,
        )
        return {"success": True, "data": result}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ── Main message processing ───────────────────────────────────────────────

async def process_message(user_id: str, text: str, connection) -> str:
    """Send a user message through OpenAI with Storefront + Composio tools.

    Args:
        user_id: The sender's identifier (used for session + Composio entity).
        text: The user's natural-language message.
        connection: A ShopifyConnection instance (must be authenticated).

    Returns:
        The assistant's text response.
    """
    composio_tools = connection.get_tools()
    openai_tools = _build_openai_tools(composio_tools)

    history = get_history(user_id)

    # Build messages: system prompt + history + new user message
    messages = [{"role": "system", "content": SHOPIFY_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": text})

    # Tool-call loop: keep going until OpenAI returns a plain text response
    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=openai_tools if openai_tools else None,
        )

        choice = response.choices[0]
        assistant_message = choice.message

        # Append the assistant's message to the conversation
        messages.append(assistant_message.model_dump(exclude_none=True))

        # If no tool calls, we're done
        if not assistant_message.tool_calls:
            break

        # Execute each tool call and append results
        for tool_call in assistant_message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

            result = _execute_tool(
                connection.composio,
                user_id,
                name,
                args,
            )

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

    # Persist history (skip the system prompt)
    _sessions[user_id] = messages[1:]

    return assistant_message.content or ""
