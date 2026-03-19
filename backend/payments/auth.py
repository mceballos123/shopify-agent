import os
from dotenv import load_dotenv
from .session import create_payment_session
from .idempotency import generate_source_identifier

load_dotenv()

SHOP_PAY_CLIENT_ID = os.getenv("SHOP_PAY_CLIENT_ID", "")
SHOPIFY_STORE_DOMAIN = os.getenv("SHOPIFY_STORE_DOMAIN", "")


def get_frontend_config() -> dict:
    
    return {
        "shop_pay_client_id": SHOP_PAY_CLIENT_ID,
        "store_domain": SHOPIFY_STORE_DOMAIN,
    }


def create_auth_session(
    line_items: list[dict],
    source_identifier: str | None = None,
    **kwargs,
) -> dict:
    
    if source_identifier is None:
        source_identifier = generate_source_identifier()

    return create_payment_session(
        line_items,
        source_identifier=source_identifier,
        **kwargs,
    )
