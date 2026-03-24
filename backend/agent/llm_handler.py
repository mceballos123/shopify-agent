"""
Gemini LLM handler with Composio Shopify tools and stateful sessions.

Manages per-user conversation history and processes natural-language
messages through Gemini, which dynamically calls Composio Shopify tools
instead of hardcoded action handlers.
"""

import os
import json
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

SYSTEM_INSTRUCTION = (
    "You are a Shopify shopping assistant. You help users manage their "
    "Shopify store carts: creating carts, adding/updating/removing items, "
    "setting buyer identity, and checking out. Use the available Shopify "
    "tools to fulfill user requests. Be concise and helpful. "
    "If a tool call fails, explain the error clearly to the user."
)


# ── Per-user session store (stateful across refreshes) ─────────────────────

_sessions: dict[str, list] = {}


def get_history(user_id: str) -> list:
    """Return stored Gemini conversation history for a user."""
    return _sessions.get(user_id, [])


def clear_history(user_id: str) -> None:
    """Clear a user's conversation history."""
    _sessions.pop(user_id, None)


# ── Composio -> Gemini tool conversion ─────────────────────────────────────

def _convert_tools(composio_tools: list) -> Optional[list]:
    """Convert Composio (OpenAI-format) tools to Gemini function declarations."""
    if not composio_tools:
        return None
    declarations = []
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


# ── Composio tool execution ────────────────────────────────────────────────

def _execute_tool(composio_client, user_id: str, name: str, args: dict) -> dict:
    """Execute a single Composio tool call and return the result."""
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
    """Send a user message through Gemini with Composio Shopify tools.

    Args:
        user_id: The sender's identifier (used for session + Composio entity).
        text: The user's natural-language message.
        connection: A ShopifyConnection instance (must be authenticated).

    Returns:
        The assistant's text response.
    """
    composio_tools = connection.get_tools()
    gemini_tools = _convert_tools(composio_tools)

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        tools=gemini_tools,
        system_instruction=SYSTEM_INSTRUCTION,
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
