import sys
import requests
from payments import (
    create_payment_session,
    submit_payment,
    generate_idempotency_key,
    ShopPayAPIError,
)


def main():
    example_items = [
        {"label": "AI Agent Monthly Plan", "quantity": 1, "price": "29.99", "sku": "AGENT-001"},
    ]

    print("--- Creating payment session ---")
    try:
        session = create_payment_session(example_items)
        print(f"Session token: {session['token']}")
        print(f"Checkout URL:  {session['checkout_url']}")
        print(f"Source ID:     {session['source_identifier']}")

        print("\n--- Submitting payment ---")
        idem_key = generate_idempotency_key()
        print(f"Idempotency key: {idem_key}")

        receipt = submit_payment(
            session_token=session["token"],
            line_items=example_items,
            idempotency_key=idem_key,
            order_name="ASI-ONE-001",
        )
        print(f"Receipt token: {receipt['receipt_token']}")
        print(f"Status:        {receipt['processing_status']}")
    except ShopPayAPIError as e:
        print(f"Shop Pay error: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
