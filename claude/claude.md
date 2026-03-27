# Shopify Agent - Session Notes

## Architecture Overview (2026-03-25)

A conversational Shopify cart agent. Users browse the store's inventory via the Storefront GraphQL API and manage a shopping cart through natural language. No login is required upfront — when the user is done shopping, the agent provides a Shopify checkout URL where the user signs in and completes payment. **Shopify handles all payments and authentication at checkout, not this application**.

### Flow
1. User connects via HTTP or ASI1 chat protocol
2. User messages go to OpenAI LLM with Storefront API tools
3. OpenAI calls the appropriate tools to fulfill the user's request (browse products, manage cart)
4. When the user is done, agent returns the cart's `checkoutUrl` — user signs in on Shopify's checkout page

### Backend structure
```
shopify-agent/
├── backend/
│   ├── .env                        # Shopify + OpenAI credentials (gitignored)
│   ├── .env.example                # Credential template
│   ├── server.py                   # FastAPI app — chat endpoint + session cookies
│   │
│   ├── graphql/
│   │   ├── __init__.py             # Re-exports client, tools, queries, mutations
│   │   ├── client.py              # execute_graphql() — Storefront API HTTP client
│   │   ├── tools.py               # Storefront ops as OpenAI-callable tools
│   │   ├── declarations.py        # OpenAI function declarations for tools
│   │   ├── mutations.py            # CART_CREATE, CART_LINES_ADD/UPDATE/REMOVE,
│   │   │                           # CART_BUYER_IDENTITY_UPDATE, CART_ATTRIBUTES_UPDATE
│   │   └── queries.py              # CART_QUERY, PRODUCTS_QUERY
│   │
│   ├── agent/
│   │   ├── __init__.py             # Re-exports chat_protocol
│   │   ├── shopify_agent.py        # Agent entry point — creates Agent, includes protocol, runs
│   │   ├── chat_protocol.py        # ASI1 Chat protocol — routes messages to OpenAI
│   │   └── llm_handler.py          # OpenAI LLM with Storefront tools, stateful sessions
│   │
├── claude/
│   └── claude.md                   # Session notes / architecture (this file)
│
└── skill/styles/
    └── SKILL.md
```

### API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send message to OpenAI shopping assistant |
| GET | `/health` | Health check |

### OpenAI Tools Available to the Agent
| Tool | Description |
|------|-------------|
| `get_products` | Browse the store's product catalog |
| `get_cart` | Fetch current cart state |
| `create_cart` | Create a new cart with line items |
| `add_lines` | Add items to an existing cart |
| `update_lines` | Update quantities/variants in a cart |
| `remove_lines` | Remove items from a cart |
| `update_buyer_identity` | Set buyer email/phone/country on a cart |

### uAgent Protocol (ASI1 Chat)
Uses the standard ASI1 `ChatMessage` protocol. Messages are routed directly to OpenAI + Storefront tools pipeline.

### Config needed (.env)
- `SHOPIFY_STORE_DOMAIN` — e.g. your-store.myshopify.com
- `SHOPIFY_STOREFRONT_ACCESS_TOKEN` — Storefront API access token
- `SHOPIFY_API_VERSION` — e.g. 2024-10
- `OPENAI_API_KEY` — OpenAI API key
- `OPENAI_MODEL` — OpenAI model to use (default: gpt-4o)
- `SHOPIFY_AGENT_SEED` — seed phrase for deterministic agent address
- `SHOPIFY_AGENT_PORT` — port the agent listens on (default 8001)
- `SHOPIFY_AGENT_ENDPOINT` — public endpoint for agent communication
