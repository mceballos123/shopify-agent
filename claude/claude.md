# Shopify Agent - Session Notes

## Shop Pay Payment Integration (2026-03-16)

Implemented Shop Pay checkout integration using the Shopify Storefront GraphQL API (Commerce Components / Pay SDK).

### What was built
- **Idempotent payment submission** — UUID v4-based idempotency keys ensure payments are processed exactly once, even on retries
- **Payment session creation** — `shopPayPaymentRequestSessionCreate` mutation to initialize a Shop Pay checkout session (returns token + checkout URL)
- **Payment session submission** — `shopPayPaymentRequestSessionSubmit` mutation to confirm/charge the payment
- **Payment request builder** — Constructs `ShopPayPaymentRequestInput` from simple line item dicts (handles line pricing, shipping, delivery methods, totals)

### Backend structure (current as of 2026-03-17)
```
shopify-agent/
├── backend/
│   ├── .env                        # Shopify credentials (gitignored)
│   ├── .env.example                # Credential template
│   ├── main.py                     # CLI entry point (demo / smoke-test)
│   ├── server.py                   # FastAPI app — HTTP routes
│   ├── requirements.txt            # Python dependencies
│   │
│   ├── graphql/
│   │   ├── __init__.py
│   │   ├── mutations.py            # SESSION_CREATE_MUTATION, SESSION_SUBMIT_MUTATION
│   │   └── queries.py              # RECEIPT_LOOKUP_QUERY
│   │
│   ├── payments/
│   │   ├── __init__.py             # Re-exports all public symbols
│   │   ├── auth.py                 # get_frontend_config(), create_auth_session()
│   │   ├── builder.py              # build_payment_request()
│   │   ├── callback.py             # verify_payment_receipt(), handle_payment_callback()
│   │   ├── client.py               # execute_graphql(), ShopPayAPIError
│   │   ├── idempotency.py          # generate_idempotency_key(), generate_source_identifier()
│   │   ├── session.py              # create_payment_session(), get_or_create_payment_session(), submit_payment()
│   │   └── store.py                # In-memory session store — PaymentRecord, PaymentStatus
│   │
│   ├── templates/
│   │   └── checkout.html           # Checkout UI (embeds Shop Pay client SDK)
│   │
│   └── webhooks/
│       ├── __init__.py
│       └── handler.py              # verify_webhook(), handle_payment_event()
│
├── claude/
│   └── CLAUDE.md                   # Session notes / architecture (this file)
│
└── skill/styles/
    └── SKILL.md
```

## Webhook-based Idempotency Refactor (2026-03-17)

Replaced the stateless UUID-per-call approach with a Shopify webhook-driven session store to prevent duplicate charges on page refresh.

### How it works
1. **Client** stores `source_identifier` in `localStorage` after the first `POST /api/payment/session` call.
2. On every subsequent call (e.g. page refresh), the client sends the stored `source_identifier` back in the request body.
3. **Server** calls `get_or_create_payment_session()` — if an existing PENDING record exists for that `source_identifier`, the existing checkout URL is returned instead of creating a new session.
4. **Shopify webhooks** (`payment_sessions/resolve`, `payment_sessions/reject`) hit `POST /webhooks/payment`, which verifies the HMAC-SHA256 signature and updates the session status to COMPLETED or FAILED.
5. COMPLETED/FAILED sessions raise `ShopPayAPIError` if a client tries to resume them, forcing a new checkout flow.

### New files
```
backend/
├── payments/store.py          # In-memory session store (PaymentRecord, PaymentStatus)
└── webhooks/
    ├── __init__.py
    └── handler.py             # verify_webhook() + handle_payment_event()
```

### Modified files
- `payments/session.py` — `create_payment_session` saves to store; new `get_or_create_payment_session`
- `payments/__init__.py` — exports store symbols
- `server.py` — session endpoint accepts `source_identifier`; new `POST /webhooks/payment` endpoint

### Webhook registration
Register `POST /webhooks/payment` in your Shopify Partner Dashboard for topics:
- `payment_sessions/resolve`
- `payment_sessions/reject`

### Config needed (.env)
- `SHOPIFY_STORE_DOMAIN` — e.g. your-store.myshopify.com
- `SHOPIFY_STOREFRONT_ACCESS_TOKEN` — Storefront API access token
- `SHOPIFY_API_VERSION` — e.g. 2024-10
- `SHOPIFY_WEBHOOK_SECRET` — signing secret from Partner Dashboard (used for HMAC verification)
