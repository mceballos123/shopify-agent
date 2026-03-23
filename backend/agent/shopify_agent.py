"""
Shopify Cart Agent — single entry point.

Run:
    cd backend
    python -m agent.shopify_agent

Starts the FastAPI server (HTTP routes, webhooks, UI) and the uAgent
(ShopifyCartProtocol) in a single process.
"""

import os
import sys
import uvicorn

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from uagents import Agent, Context
from agent.chat_protocol import shopify_protocol
from server import app  # FastAPI app with all HTTP routes

load_dotenv()

AGENT_SEED = os.getenv("SHOPIFY_AGENT_SEED", "shopify-agent-default-seed")
AGENT_PORT = int(os.getenv("SHOPIFY_AGENT_PORT", "8001"))
AGENT_ENDPOINT = os.getenv(
    "SHOPIFY_AGENT_ENDPOINT",
    f"http://localhost:{AGENT_PORT}/submit",
)

HTTP_PORT = int(os.getenv("HTTP_PORT", "8000"))

shopify_agent = Agent(
    name="ShopifyCartAgent",
    seed=AGENT_SEED,
    port=AGENT_PORT,
    endpoint=[AGENT_ENDPOINT],
)

shopify_agent.include(shopify_protocol, publish_manifest=True)


@shopify_agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(
        f"Shopify Cart Agent started — "
        f"name={ctx.agent.name}  address={ctx.agent.address}"
    )
    ctx.logger.info(f"Agent listening on port {AGENT_PORT}")


@shopify_agent.on_event("shutdown")
async def on_shutdown(ctx: Context):
    ctx.logger.info("Shopify Cart Agent shutting down")


def main():
    """Run the FastAPI server with the uAgent protocol included."""
    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")


if __name__ == "__main__":
    main()
