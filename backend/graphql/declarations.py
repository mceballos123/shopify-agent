"""
OpenAI function declarations for Storefront GraphQL tools.

These schemas tell the LLM what tools are available and how to call them.
Kept separate from the tool implementations for readability.
"""

TOOL_DECLARATIONS = [
    {
        "name": "get_shop_info",
        "description": (
            "Fetch the store's name and description from Shopify. "
            "Use this to greet the user with the actual store name. "
            "Call this once at the start of a conversation before showing products."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_products",
        "description": (
            "Fetch products from the store catalog. Returns product titles, "
            "descriptions, images, prices, variants, and availability. "
            "Use this when the user wants to browse or search what's available."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "first": {
                    "type": "integer",
                    "description": "Number of products to return (max 50).",
                },
                "after": {
                    "type": "string",
                    "description": "Pagination cursor to fetch the next page.",
                },
            },
        },
    },
    {
        "name": "get_cart",
        "description": (
            "Fetch the current state of a cart by its ID. Returns line items, "
            "costs, checkout URL, and buyer identity."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "cart_id": {
                    "type": "string",
                    "description": "The Shopify cart ID (e.g. gid://shopify/Cart/...).",
                },
            },
            "required": ["cart_id"],
        },
    },
    {
        "name": "create_cart",
        "description": (
            "Create a new shopping cart with line items. Each line needs a "
            "merchandiseId (variant ID) and quantity. Returns the cart with "
            "its checkoutUrl."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lines": {
                    "type": "array",
                    "description": "Line items to add. Each item has merchandiseId and quantity.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "merchandiseId": {"type": "string"},
                            "quantity": {"type": "integer"},
                        },
                        "required": ["merchandiseId", "quantity"],
                    },
                },
                "buyer_identity": {
                    "type": "object",
                    "description": "Optional buyer info: email, phone, countryCode.",
                },
                "note": {
                    "type": "string",
                    "description": "Optional note for the cart.",
                },
            },
            "required": ["lines"],
        },
    },
    {
        "name": "add_lines",
        "description": "Add new line items to an existing cart.",
        "parameters": {
            "type": "object",
            "properties": {
                "cart_id": {
                    "type": "string",
                    "description": "The cart ID to add lines to.",
                },
                "lines": {
                    "type": "array",
                    "description": "Line items to add (merchandiseId + quantity).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "merchandiseId": {"type": "string"},
                            "quantity": {"type": "integer"},
                        },
                        "required": ["merchandiseId", "quantity"],
                    },
                },
            },
            "required": ["cart_id", "lines"],
        },
    },
    {
        "name": "update_lines",
        "description": "Update quantities or variants of existing line items in a cart.",
        "parameters": {
            "type": "object",
            "properties": {
                "cart_id": {
                    "type": "string",
                    "description": "The cart ID.",
                },
                "lines": {
                    "type": "array",
                    "description": "Lines to update. Each needs the line item id and new quantity.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "The cart line item ID."},
                            "quantity": {"type": "integer"},
                            "merchandiseId": {"type": "string"},
                        },
                        "required": ["id"],
                    },
                },
            },
            "required": ["cart_id", "lines"],
        },
    },
    {
        "name": "remove_lines",
        "description": "Remove line items from a cart by their line item IDs.",
        "parameters": {
            "type": "object",
            "properties": {
                "cart_id": {
                    "type": "string",
                    "description": "The cart ID.",
                },
                "line_ids": {
                    "type": "array",
                    "description": "IDs of the line items to remove.",
                    "items": {"type": "string"},
                },
            },
            "required": ["cart_id", "line_ids"],
        },
    },
    {
        "name": "update_buyer_identity",
        "description": "Set or update the buyer identity (email, phone, country) on a cart.",
        "parameters": {
            "type": "object",
            "properties": {
                "cart_id": {
                    "type": "string",
                    "description": "The cart ID.",
                },
                "buyer_identity": {
                    "type": "object",
                    "description": "Buyer info with optional email, phone, countryCode fields.",
                },
            },
            "required": ["cart_id", "buyer_identity"],
        },
    },
]
