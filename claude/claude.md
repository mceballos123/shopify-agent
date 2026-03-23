# Shopify Agent - Session Notes

## Storefront Cart API Integration (2026-03-19)

Replaced Shop Pay payment sessions with the Shopify Storefront GraphQL Cart API. Users add items to a cart and are redirected to Shopify's hosted checkout via the cart's `checkoutUrl`.

### What was built
- **Cart CRUD** — `cartCreate`, `cartLinesAdd`, `cartLinesUpdate`, `cartLinesRemove` mutations
- **Buyer Identity** — `cartBuyerIdentityUpdate` to associate email/phone/country with a cart
- **Cart Attributes** — `cartAttributesUpdate` for custom key-value metadata on carts
- **Cart Query** — `cart(id)` query to fetch full cart state including lines, cost, and buyer identity
- **Cart objects implemented** — Cart, CartLine, CartCost, Merchandise (ProductVariant), CartBuyerIdentity, Attribute

### How it works
1. Client calls `POST /api/cart` with merchandise variant IDs + quantities → creates a Storefront cart
2. Cart can be modified via `/api/cart/lines/add`, `/api/cart/lines/update`, `/api/cart/lines/remove`
3. Buyer identity set via `/api/cart/buyer-identity`, attributes via `/api/cart/attributes`
4. Client redirects to `checkoutUrl` from the cart response to complete purchase on Shopify checkout
5. Shopify webhooks (order creation, payment, cancellation) update local cart status

### Backend structure (current as of 2026-03-23)
```
shopify-agent/
├── backend/
│   ├── .env                        # Shopify credentials (gitignored)
│   ├── .env.example                # Credential template
│   ├── server.py                   # FastAPI app — HTTP routes
│   ├── models.py                   # All request & agent message models
│   │                               # (Pydantic BaseModel + uagents Model)
│   │
│   ├── graphql/
│   │   ├── __init__.py
│   │   ├── mutations.py            # CART_CREATE, CART_LINES_ADD/UPDATE/REMOVE,
│   │   │                           # CART_BUYER_IDENTITY_UPDATE, CART_ATTRIBUTES_UPDATE
│   │   └── queries.py              # CART_QUERY
│   │
│   ├── payments/
│   │   ├── __init__.py             # Re-exports all public symbols
│   │   ├── client.py               # execute_graphql(), StorefrontAPIError
│   │   ├── cart.py                 # create_cart(), add_lines(), update_lines(),
│   │   │                           # remove_lines(), update_buyer_identity(),
│   │   │                           # update_attributes(), get_cart()
│   │   └── store.py                # In-memory cart store — CartRecord, OrderStatus
│   │
│   ├── templates/
│   │   ├── checkout.html           # Checkout UI (creates cart, redirects to checkoutUrl)
│   │   └── test_dashboard.html     # Test UI for all cart endpoints
│   │
│   ├── webhooks/
│   │   ├── __init__.py
│   │   └── handler.py              # verify_webhook(), handle_order_creation/payment/cancellation
│   │
│   └── agent/
│       ├── __init__.py             # Re-exports protocol + message models
│       ├── shopify_agent.py        # Agent entry point — creates Agent, includes protocol, runs
│       └── chat_protocol.py        # Protocol definition + on_message handlers
│
├── claude/
│   └── CLAUDE.md                   # Session notes / architecture (this file)
│
└── skill/styles/
    └── SKILL.md
```

### API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/cart` | Create a new cart |
| GET | `/api/cart?cart_id=` | Fetch cart from Storefront API |
| POST | `/api/cart/lines/add` | Add lines to a cart |
| POST | `/api/cart/lines/update` | Update line quantities/variants |
| POST | `/api/cart/lines/remove` | Remove lines from a cart |
| POST | `/api/cart/buyer-identity` | Update buyer email/phone/country |
| POST | `/api/cart/attributes` | Set custom cart attributes |
| GET | `/api/cart/status` | Local store status lookup |
| GET | `/checkout` | Checkout UI page |
| GET | `/test` | Test dashboard UI |
| GET | `/health` | Health check |

### Webhook Endpoints (already registered)
| Method | Path | Shopify Topic |
|--------|------|---------------|
| POST | `/webhooks/order/payment` | ORDER_TRANSACTIONS_CREATE |
| POST | `/order/creation` | ORDERS_CREATE |
| POST | `/order/cancellation` | ORDERS_CANCELLED |

### uAgent Protocol (v0.2.0)
Actions: `create_cart`, `add_lines`, `update_lines`, `remove_lines`, `update_buyer_identity`, `update_attributes`, `get_cart`

```python
await ctx.send(SHOPIFY_AGENT_ADDRESS, ShopifyRequest(
    action="create_cart",
    lines=[{"merchandise_id": "gid://shopify/ProductVariant/123", "quantity": 1}],
    buyer_identity={"email": "user@example.com"},
))
```

### Config needed (.env)
- `SHOPIFY_STORE_DOMAIN` — e.g. your-store.myshopify.com
- `SHOPIFY_STOREFRONT_ACCESS_TOKEN` — Storefront API access token
- `SHOPIFY_API_VERSION` — e.g. 2024-10
- `SHOPIFY_WEBHOOK_SECRET` — signing secret from Partner Dashboard
- `SHOPIFY_AGENT_SEED` — seed phrase for deterministic agent address
- `SHOPIFY_AGENT_PORT` — port the agent listens on (default 8001)
- `SHOPIFY_AGENT_ENDPOINT` — public endpoint for agent communication
