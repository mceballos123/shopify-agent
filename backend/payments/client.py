import os
import requests
from dotenv import load_dotenv

load_dotenv()

SHOPIFY_STORE_DOMAIN = os.getenv("SHOPIFY_STORE_DOMAIN", "your-store.myshopify.com")
SHOPIFY_STOREFRONT_ACCESS_TOKEN = os.getenv("SHOPIFY_STOREFRONT_ACCESS_TOKEN", "")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION")

GRAPHQL_URL = f"https://{SHOPIFY_STORE_DOMAIN}/api/{SHOPIFY_API_VERSION}/graphql.json"

HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Storefront-Access-Token": SHOPIFY_STOREFRONT_ACCESS_TOKEN,
}


class ShopPayAPIError(Exception):
    pass


def execute_graphql(query: str, variables: dict) -> dict:
    """Execute a GraphQL mutation against the Shopify Storefront API."""
    payload = {"query": query, "variables": variables}
    response = requests.post(GRAPHQL_URL, json=payload, headers=HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "errors" in data:
        raise ShopPayAPIError(f"GraphQL errors: {data['errors']}")

    return data["data"]
