"""
Storefront API client for the agent's Shopify store.

Executes GraphQL queries and mutations against the Shopify Storefront API
using the store domain and access token from environment variables.
"""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

_STORE_DOMAIN = os.getenv("SHOPIFY_STORE_DOMAIN", "")
_ACCESS_TOKEN = os.getenv("SHOPIFY_STOREFRONT_ACCESS_TOKEN", "")
_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2024-10")

_ENDPOINT = f"https://{_STORE_DOMAIN}/api/{_API_VERSION}/graphql.json"


class StorefrontAPIError(Exception):
    pass


def execute_graphql(query: str, variables: dict | None = None) -> dict:
    """Execute a GraphQL operation against the Storefront API.

    Args:
        query: The GraphQL query or mutation string.
        variables: Optional variables for the operation.

    Returns:
        The 'data' portion of the response.

    Raises:
        StorefrontAPIError: On network errors or GraphQL errors.
    """
    headers = {
        "X-Shopify-Storefront-Access-Token": _ACCESS_TOKEN,
        "Content-Type": "application/json",
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        resp = httpx.post(_ENDPOINT, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise StorefrontAPIError(f"Storefront API request failed: {exc}") from exc

    body = resp.json()
    if "errors" in body:
        msgs = [e.get("message", str(e)) for e in body["errors"]]
        raise StorefrontAPIError(f"GraphQL errors: {'; '.join(msgs)}")

    return body.get("data", {})
