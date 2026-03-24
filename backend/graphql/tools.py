"""
Storefront GraphQL operations exposed as Gemini-callable tools.

Each function wraps a Storefront API GraphQL operation. TOOL_EXECUTORS
maps tool names to their implementation. Gemini function declarations
live in declarations.py.
"""

from graphql.client import execute_graphql
from graphql.mutations import (
    CART_CREATE_MUTATION,
    CART_LINES_ADD_MUTATION,
    CART_LINES_UPDATE_MUTATION,
    CART_LINES_REMOVE_MUTATION,
    CART_BUYER_IDENTITY_UPDATE_MUTATION,
    CART_ATTRIBUTES_UPDATE_MUTATION,
)
from graphql.queries import CART_QUERY, PRODUCTS_QUERY


# ── Tool implementations ─────────────────────────────────────────────────────

def get_products(first: int = 20, after: str | None = None) -> dict:
    """Fetch products from the agent's store."""
    variables = {"first": first}
    if after:
        variables["after"] = after
    return execute_graphql(PRODUCTS_QUERY, variables)


def get_cart(cart_id: str) -> dict:
    """Fetch a cart by ID."""
    return execute_graphql(CART_QUERY, {"id": cart_id})


def create_cart(lines: list, buyer_identity: dict | None = None,
                attributes: list | None = None, note: str | None = None) -> dict:
    """Create a new cart with the given line items."""
    cart_input: dict = {"lines": lines}
    if buyer_identity:
        cart_input["buyerIdentity"] = buyer_identity
    if attributes:
        cart_input["attributes"] = attributes
    if note:
        cart_input["note"] = note
    data = execute_graphql(CART_CREATE_MUTATION, {"input": cart_input})
    return data.get("cartCreate", {})


def add_lines(cart_id: str, lines: list) -> dict:
    """Add line items to an existing cart."""
    data = execute_graphql(CART_LINES_ADD_MUTATION, {"cartId": cart_id, "lines": lines})
    return data.get("cartLinesAdd", {})


def update_lines(cart_id: str, lines: list) -> dict:
    """Update line items in an existing cart."""
    data = execute_graphql(CART_LINES_UPDATE_MUTATION, {"cartId": cart_id, "lines": lines})
    return data.get("cartLinesUpdate", {})


def remove_lines(cart_id: str, line_ids: list) -> dict:
    """Remove line items from a cart."""
    data = execute_graphql(CART_LINES_REMOVE_MUTATION, {"cartId": cart_id, "lineIds": line_ids})
    return data.get("cartLinesRemove", {})


def update_buyer_identity(cart_id: str, buyer_identity: dict) -> dict:
    """Update buyer identity (email, phone, country) on a cart."""
    data = execute_graphql(
        CART_BUYER_IDENTITY_UPDATE_MUTATION,
        {"cartId": cart_id, "buyerIdentity": buyer_identity},
    )
    return data.get("cartBuyerIdentityUpdate", {})


def update_attributes(cart_id: str, attributes: list) -> dict:
    """Update custom attributes on a cart."""
    data = execute_graphql(
        CART_ATTRIBUTES_UPDATE_MUTATION,
        {"cartId": cart_id, "attributes": attributes},
    )
    return data.get("cartAttributesUpdate", {})


# ── Name -> function mapping for execution ────────────────────────────────────

TOOL_EXECUTORS = {
    "get_products": get_products,
    "get_cart": get_cart,
    "create_cart": create_cart,
    "add_lines": add_lines,
    "update_lines": update_lines,
    "remove_lines": remove_lines,
    "update_buyer_identity": update_buyer_identity,
}
