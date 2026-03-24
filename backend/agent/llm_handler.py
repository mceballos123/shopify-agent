"""
Gemini LLM handler with Storefront + Composio Shopify tools and stateful sessions.

Manages per-user conversation history and processes natural-language
messages through Gemini, which can call:
  - Storefront tools (browse products, manage cart) via graphql/tools.py
  - Composio Shopify tools (OAuth-gated admin actions) dynamically
"""

import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

from graphql.declarations import TOOL_DECLARATIONS as STOREFRONT_TOOLS
from graphql.tools import TOOL_EXECUTORS

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

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
    """Return stored Gemini conversation history for a user."""
    return _sessions.get(user_id, [])


def clear_history(user_id: str) -> None:
    """Clear a user's conversation history."""
    _sessions.pop(user_id, None)


# ── Tool merging: Storefront + Composio ───────────────────────────────────

def _build_gemini_tools(composio_tools: list | None) -> list:
    """Merge storefront tool declarations with Composio tool declarations."""
    declarations = list(STOREFRONT_TOOLS)

    if composio_tools:
        for tool in composio_tools:
            func = tool.get("function", tool)
            decl = {
                "name": func["name"],
                "description": func.get("description", ""),
            }
            params = func.get("parameters")
            if params:
                decl["parameters"] = params
            declarations.append(decl)

    return [{"function_declarations": declarations}]


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

def _has_function_call(response) -> bool:
    """Check whether a Gemini response contains at least one function call."""
    try:
        for part in response.candidates[0].content.parts:
            if part.function_call and part.function_call.name:
                return True
    except (IndexError, AttributeError):
        pass
    return False


async def process_message(user_id: str, text: str, connection) -> str:
    """Send a user message through Gemini with Storefront + Composio tools.

    Args:
        user_id: The sender's identifier (used for session + Composio entity).
        text: The user's natural-language message.
        connection: A ShopifyConnection instance (must be authenticated).

    Returns:
        The assistant's text response.
    """
    composio_tools = connection.get_tools()
    gemini_tools = _build_gemini_tools(composio_tools)

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        tools=gemini_tools,
        system_instruction=SHOPIFY_PROMPT,
    )

    history = get_history(user_id)
    chat = model.start_chat(history=history)

    response = chat.send_message(text)

    # Tool-call loop: keep going until Gemini returns plain text
    while _has_function_call(response):
        tool_responses = []
        for part in response.candidates[0].content.parts:
            if not part.function_call or not part.function_call.name:
                continue
            fc = part.function_call
            result = _execute_tool(
                connection.composio,
                user_id,
                fc.name,
                dict(fc.args) if fc.args else {},
            )
            tool_responses.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=fc.name,
                        response={"result": json.dumps(result)},
                    )
                )
            )

        response = chat.send_message(
            genai.protos.Content(parts=tool_responses)
        )

    # Persist updated history so sessions survive page refreshes
    _sessions[user_id] = list(chat.history)

    return response.text
