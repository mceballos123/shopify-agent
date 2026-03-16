# Shopify Agent - Session Notes

## Shop Pay Payment Integration (2026-03-16)

Implemented Shop Pay checkout integration using the Shopify Storefront GraphQL API (Commerce Components / Pay SDK).

### What was built
- **Idempotent payment submission** — UUID v4-based idempotency keys ensure payments are processed exactly once, even on retries
- **Payment session creation** — `shopPayPaymentRequestSessionCreate` mutation to initialize a Shop Pay checkout session (returns token + checkout URL)
- **Payment session submission** — `shopPayPaymentRequestSessionSubmit` mutation to confirm/charge the payment
- **Payment request builder** — Constructs `ShopPayPaymentRequestInput` from simple line item dicts (handles line pricing, shipping, delivery methods, totals)

### Backend structure
```
backend/
├── .env                       # Shopify credentials (placeholders, gitignored)
├── main.py                    # Entry point
├── requirements.txt           # requests, python-dotenv
├── graphql/
│   ├── __init__.py
│   └── mutations.py           # SESSION_CREATE_MUTATION, SESSION_SUBMIT_MUTATION
└── payments/
    ├── __init__.py
    ├── client.py              # GraphQL client + Storefront API auth
    ├── idempotency.py         # Idempotency key + source identifier generators
    ├── builder.py             # build_payment_request()
    └── session.py             # create_payment_session(), submit_payment()
```

### Config needed (.env)
- `SHOPIFY_STORE_DOMAIN` — e.g. your-store.myshopify.com
- `SHOPIFY_STOREFRONT_ACCESS_TOKEN` — Storefront API access token
- `SHOPIFY_API_VERSION` — e.g. 2024-10
