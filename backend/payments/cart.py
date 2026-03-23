"""
Storefront Cart API operations.

Wraps the Shopify Storefront GraphQL Cart mutations/queries into
simple Python functions that the server and agent can call.
"""

from .client import execute_graphql, StorefrontAPIError
from .store import CartRecord, save_cart
from graphql.mutations import (
    CART_CREATE_MUTATION,
    CART_LINES_ADD_MUTATION,
    CART_LINES_UPDATE_MUTATION,
    CART_LINES_REMOVE_MUTATION,
    CART_BUYER_IDENTITY_UPDATE_MUTATION,
    CART_ATTRIBUTES_UPDATE_MUTATION,
)
from graphql.queries import CART_QUERY, PRODUCTS_QUERY


def _parse_cart(raw: dict) -> dict:
    """Normalise the raw Cart GraphQL response into a flat dict."""
    lines = []
    for edge in raw.get("lines", {}).get("edges", []):
        node = edge["node"]
        merch = node.get("merchandise", {})
        product = merch.get("product", {})
        image = merch.get("image") or {}
        lines.append({
            "id": node["id"],
            "quantity": node["quantity"],
            "variant_id": merch.get("id"),
            "variant_title": merch.get("title"),
            "price": merch.get("price", {}),
            "product_title": product.get("title"),
            "product_handle": product.get("handle"),
            "image_url": image.get("url"),
            "image_alt": image.get("altText"),
            "attributes": node.get("attributes", []),
        })

    cost = raw.get("cost", {})
    buyer = raw.get("buyerIdentity", {})

    return {
        "id": raw["id"],
        "checkout_url": raw.get("checkoutUrl"),
        "created_at": raw.get("createdAt"),
        "updated_at": raw.get("updatedAt"),
        "total_quantity": raw.get("totalQuantity", 0),
        "note": raw.get("note"),
        "lines": lines,
        "cost": {
            "total": cost.get("totalAmount", {}),
            "subtotal": cost.get("subtotalAmount", {}),
            "total_tax": cost.get("totalTaxAmount"),
            "total_duty": cost.get("totalDutyAmount"),
        },
        "buyer_identity": {
            "email": buyer.get("email"),
            "phone": buyer.get("phone"),
            "country_code": buyer.get("countryCode"),
        },
        "attributes": raw.get("attributes", []),
    }


def _check_user_errors(payload: dict, operation: str) -> None:
    errors = payload.get("userErrors", [])
    if errors:
        raise StorefrontAPIError(f"{operation} errors: {errors}")


def create_cart(
    lines: list[dict],
    buyer_identity: dict | None = None,
    attributes: list[dict] | None = None,
    note: str | None = None,
) -> dict:
    """
    Create a new Storefront cart.

    Each item in `lines` should have:
      - merchandise_id: str  (Shopify product variant GID)
      - quantity: int
      - attributes: list[dict] (optional, each {key, value})
    """
    cart_lines = []
    for item in lines:
        line = {
            "merchandiseId": item["merchandise_id"],
            "quantity": item.get("quantity", 1),
        }
        if item.get("attributes"):
            line["attributes"] = [
                {"key": a["key"], "value": a["value"]}
                for a in item["attributes"]
            ]
        cart_lines.append(line)

    cart_input: dict = {"lines": cart_lines}

    if buyer_identity:
        bi: dict = {}
        if buyer_identity.get("email"):
            bi["email"] = buyer_identity["email"]
        if buyer_identity.get("phone"):
            bi["phone"] = buyer_identity["phone"]
        if buyer_identity.get("country_code"):
            bi["countryCode"] = buyer_identity["country_code"]
        if buyer_identity.get("customer_access_token"):
            bi["customerAccessToken"] = buyer_identity["customer_access_token"]
        if bi:
            cart_input["buyerIdentity"] = bi

    if attributes:
        cart_input["attributes"] = [
            {"key": a["key"], "value": a["value"]} for a in attributes
        ]

    if note:
        cart_input["note"] = note

    result = execute_graphql(CART_CREATE_MUTATION, {"input": cart_input})
    data = result["cartCreate"]
    _check_user_errors(data, "cartCreate")

    cart = _parse_cart(data["cart"])

    # Persist locally so webhooks can correlate orders back to carts
    record = CartRecord(
        cart_id=cart["id"],
        checkout_url=cart["checkout_url"],
    )
    # Store source_identifier from attributes if provided
    for attr in (attributes or []):
        if attr["key"] == "source_identifier":
            record.source_identifier = attr["value"]
    save_cart(record)

    return cart


def add_lines(cart_id: str, lines: list[dict]) -> dict:
    """
    Add merchandise lines to an existing cart.

    Each item in `lines`: {merchandise_id, quantity?, attributes?}
    """
    cart_lines = []
    for item in lines:
        line = {
            "merchandiseId": item["merchandise_id"],
            "quantity": item.get("quantity", 1),
        }
        if item.get("attributes"):
            line["attributes"] = [
                {"key": a["key"], "value": a["value"]}
                for a in item["attributes"]
            ]
        cart_lines.append(line)

    result = execute_graphql(CART_LINES_ADD_MUTATION, {
        "cartId": cart_id,
        "lines": cart_lines,
    })
    data = result["cartLinesAdd"]
    _check_user_errors(data, "cartLinesAdd")
    return _parse_cart(data["cart"])


def update_lines(cart_id: str, lines: list[dict]) -> dict:
    """
    Update existing cart lines (change quantity, swap variant, etc.).

    Each item in `lines`: {id (line ID), quantity?, merchandise_id?, attributes?}
    """
    update_lines_input = []
    for item in lines:
        line: dict = {"id": item["id"]}
        if "quantity" in item:
            line["quantity"] = item["quantity"]
        if "merchandise_id" in item:
            line["merchandiseId"] = item["merchandise_id"]
        if item.get("attributes"):
            line["attributes"] = [
                {"key": a["key"], "value": a["value"]}
                for a in item["attributes"]
            ]
        update_lines_input.append(line)

    result = execute_graphql(CART_LINES_UPDATE_MUTATION, {
        "cartId": cart_id,
        "lines": update_lines_input,
    })
    data = result["cartLinesUpdate"]
    _check_user_errors(data, "cartLinesUpdate")
    return _parse_cart(data["cart"])


def remove_lines(cart_id: str, line_ids: list[str]) -> dict:
    """Remove lines from a cart by their line IDs."""
    result = execute_graphql(CART_LINES_REMOVE_MUTATION, {
        "cartId": cart_id,
        "lineIds": line_ids,
    })
    data = result["cartLinesRemove"]
    _check_user_errors(data, "cartLinesRemove")
    return _parse_cart(data["cart"])


def update_buyer_identity(cart_id: str, buyer_identity: dict) -> dict:
    """
    Update buyer identity on a cart.

    buyer_identity fields: email, phone, country_code, customer_access_token
    """
    bi: dict = {}
    if buyer_identity.get("email"):
        bi["email"] = buyer_identity["email"]
    if buyer_identity.get("phone"):
        bi["phone"] = buyer_identity["phone"]
    if buyer_identity.get("country_code"):
        bi["countryCode"] = buyer_identity["country_code"]
    if buyer_identity.get("customer_access_token"):
        bi["customerAccessToken"] = buyer_identity["customer_access_token"]

    result = execute_graphql(CART_BUYER_IDENTITY_UPDATE_MUTATION, {
        "cartId": cart_id,
        "buyerIdentity": bi,
    })
    data = result["cartBuyerIdentityUpdate"]
    _check_user_errors(data, "cartBuyerIdentityUpdate")
    return _parse_cart(data["cart"])


def update_attributes(cart_id: str, attributes: list[dict]) -> dict:
    """
    Update custom attributes on a cart.

    Each attribute: {key: str, value: str}
    """
    result = execute_graphql(CART_ATTRIBUTES_UPDATE_MUTATION, {
        "cartId": cart_id,
        "attributes": [{"key": a["key"], "value": a["value"]} for a in attributes],
    })
    data = result["cartAttributesUpdate"]
    _check_user_errors(data, "cartAttributesUpdate")
    return _parse_cart(data["cart"])


def get_cart(cart_id: str) -> dict:
    """Fetch a cart by its ID."""
    result = execute_graphql(CART_QUERY, {"id": cart_id})
    raw = result.get("cart")
    if not raw:
        raise StorefrontAPIError(f"Cart not found: {cart_id}")
    return _parse_cart(raw)


def get_products(first: int = 20, after: str | None = None) -> dict:
    """Fetch a paginated list of products with their variants."""
    variables: dict = {"first": first}
    if after:
        variables["after"] = after

    result = execute_graphql(PRODUCTS_QUERY, variables)
    connection = result.get("products", {})

    products = []
    for edge in connection.get("edges", []):
        node = edge["node"]
        images = [
            {"url": img["node"]["url"], "alt_text": img["node"].get("altText")}
            for img in node.get("images", {}).get("edges", [])
        ]
        variants = [
            {
                "id": v["node"]["id"],
                "title": v["node"]["title"],
                "price": v["node"]["price"],
                "available_for_sale": v["node"]["availableForSale"],
            }
            for v in node.get("variants", {}).get("edges", [])
        ]
        products.append({
            "id": node["id"],
            "title": node["title"],
            "description": node.get("description", ""),
            "handle": node.get("handle", ""),
            "images": images,
            "price_range": node.get("priceRange", {}),
            "variants": variants,
        })

    page_info = connection.get("pageInfo", {})
    return {
        "products": products,
        "has_next_page": page_info.get("hasNextPage", False),
        "end_cursor": page_info.get("endCursor"),
    }
