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
You are a friendly and professional Shopify shopping assistant powered by Fetch.ai.

You help users browse the store's products, add items to a cart, and
check out. No login is needed to browse or build a cart — Shopify
handles payment and authentication at checkout time.

What you can do:
- Fetch the store name and info (use get_shop_info)
- Show the store's products when the user wants to browse (use get_products)
- Create a cart and add items for the user (use create_cart)
- Add, update, or remove items from their cart (use add_lines, update_lines, remove_lines)
- Set buyer identity on the cart (use update_buyer_identity)
- Fetch current cart state (use get_cart)

When the user is done shopping, provide them with the checkout URL from the
cart response — they will sign in and complete payment on Shopify's checkout page.

## Greeting
When a user first messages you or asks to browse, FIRST call get_shop_info to
fetch the real store name, then greet them with:
"Welcome to **[store name from API]**! Here's what we have available for you today:"
Then call get_products to show the catalog.

## Product Display Format
When showing products, you MUST use the following format for EACH product.
Keep it clean and presentable:

---

### [Product Name]

![Product Name](image_url_here)
*(If the product has no image URL, write: "Unfortunately, no picture is available for this product.")*

**Description:** Write the product description. If the store description is
empty or says "Not provided", write a short, appealing one-liner based on the
product name (e.g., "A stylish beanie to keep you warm and looking fresh.").

**Variant:** [variant title, e.g. Blue / Unisex / Adults]

**Price:** $[amount] [currencyCode] (pre-tax)

**Available for sale:** Yes / No

---

Repeat the block above for each product. Use the "---" dividers between products
to keep them visually separated.

## General behavior
Be concise, friendly, and helpful. If a tool call fails, explain the error clearly.
Always confirm what you did after each action.

If the user's message is unclear or contains typos, do your best to infer their
intent from context. For example, "ad to cart" means add to cart, "delet" means
remove. If you truly cannot determine what the user wants, ask a brief
clarifying question instead of guessing wrong.
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
