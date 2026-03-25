# Shopify Agent - Session Notes

## Architecture Overview (2026-03-23)

A conversational Shopify cart agent. Users log into their Shopify account via Composio OAuth, then browse the agent's store inventory via the Storefront GraphQL API. They can add, update, or remove items from their cart through natural language. When done, the agent provides a Shopify checkout link — **Shopify handles all payments, not this application**.

### Flow
1. User connects via HTTP or ASI1 chat protocol
2. Agent checks Composio OAuth status — if not connected, initiates OAuth and returns auth link
3. Once authenticated, user messages go to OpenAI LLM with two sets of tools:
   - **Storefront tools** — browse products, create/manage cart (via `graphql/tools.py`)
   - **Composio tools** — dynamic Shopify admin actions (via Composio SDK)
4. OpenAI calls the appropriate tools to fulfill the user's request
5. When the user is done, agent returns the cart's `checkoutUrl` — Shopify handles payment

### Backend structure
```
shopify-agent/
├── backend/
│   ├── .env                        # Shopify + Composio + OpenAI credentials (gitignored)
│   ├── .env.example                # Credential template
│   ├── server.py                   # FastAPI app — OAuth and chat routes
│   │
│   ├── graphql/
│   │   ├── __init__.py             # Re-exports client, tools, queries, mutations
│   │   ├── client.py              # execute_graphql() — Storefront API HTTP client
│   │   ├── tools.py               # Storefront ops as OpenAI-callable tools + declarations
│   │   ├── mutations.py            # CART_CREATE, CART_LINES_ADD/UPDATE/REMOVE,
│   │   │                           # CART_BUYER_IDENTITY_UPDATE, CART_ATTRIBUTES_UPDATE
│   │   └── queries.py              # CART_QUERY, PRODUCTS_QUERY
│   │
│   ├── agent/
│   │   ├── __init__.py             # Re-exports chat_protocol
│   │   ├── shopify_agent.py        # Agent entry point — creates Agent, includes protocol, runs uvicorn
│   │   ├── chat_protocol.py        # ASI1 Chat protocol — OAuth gate + OpenAI routing
│   │   ├── llm_handler.py          # OpenAI LLM with Storefront + Composio tools, stateful sessions
│   │   └── session_manager.py      # HTTP session manager — cookie-based OAuth + session persistence
│   │
│   └── composio_auth/
│       ├── __init__.py             # Re-exports ShopifyConnection, get/create helpers
│       └── shopify_connection.py   # Per-user Shopify OAuth via Composio
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
| GET | `/api/auth/status` | Check if current session has active Shopify OAuth |
| POST | `/api/auth/initiate` | Start Shopify OAuth flow, returns redirect URL |
| POST | `/api/chat` | Send message to OpenAI assistant (requires OAuth) |
| GET | `/health` | Health check |

### OpenAI Tools Available to the Agent
| Tool | Source | Description |
|------|--------|-------------|
| `get_products` | Storefront | Browse the store's product catalog |
| `get_cart` | Storefront | Fetch current cart state |
| `create_cart` | Storefront | Create a new cart with line items |
| `add_lines` | Storefront | Add items to an existing cart |
| `update_lines` | Storefront | Update quantities/variants in a cart |
| `remove_lines` | Storefront | Remove items from a cart |
| `update_buyer_identity` | Storefront | Set buyer email/phone/country on a cart |
| *(dynamic)* | Composio | Any Shopify admin actions available via Composio SDK |

### uAgent Protocol (ASI1 Chat)
Uses the standard ASI1 `ChatMessage` protocol. Messages are routed through the same OAuth gate and OpenAI + tools pipeline as HTTP requests.

### Config needed (.env)
- `SHOPIFY_STORE_DOMAIN` — e.g. your-store.myshopify.com
- `SHOPIFY_STOREFRONT_ACCESS_TOKEN` — Storefront API access token
- `SHOPIFY_API_VERSION` — e.g. 2024-10
- `COMPOSIO_API_KEY` — Composio API key
- `SHOPIFY_AUTH_CONFIG_ID` — Composio auth config for Shopify OAuth
- `OPENAI_API_KEY` — OpenAI API key
- `OPENAI_MODEL` — OpenAI model to use (default: gpt-4o)
- `SHOPIFY_AGENT_SEED` — seed phrase for deterministic agent address
- `SHOPIFY_AGENT_PORT` — port the agent listens on (default 8001)
- `SHOPIFY_AGENT_ENDPOINT` — public endpoint for agent communication
- `HTTP_PORT` — FastAPI server port (default 8000)
