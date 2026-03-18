"""
Shopify Payment Agent — entry point.

Run:
    cd backend
    python -m agent.shopify_agent

The agent registers the ShopifyPaymentProtocol so other uAgents can
send ShopifyRequest messages to create sessions, check status, and
submit payments through the existing Shop Pay integration.
"""

import os
import sys

# Ensure backend root is on the path so `payments.*` imports resolve
# regardless of how the script is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from uagents import Agent, Context
from agent.chat_protocol import shopify_protocol

AGENT_SEED = os.getenv("SHOPIFY_AGENT_SEED", "shopify-agent-default-seed")
AGENT_PORT = int(os.getenv("SHOPIFY_AGENT_PORT", "8001"))
AGENT_ENDPOINT = os.getenv(
    "SHOPIFY_AGENT_ENDPOINT",
    f"http://localhost:{AGENT_PORT}/submit",
)

shopify_agent = Agent(
    name="ShopifyPaymentAgent",
    seed=AGENT_SEED,
    port=AGENT_PORT,
    endpoint=[AGENT_ENDPOINT],
)

shopify_agent.include(shopify_protocol, publish_manifest=True)


@shopify_agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(
        f"Shopify Payment Agent started — "
        f"name={ctx.agent.name}  address={ctx.agent.address}"
    )
    ctx.logger.info(f"Listening on port {AGENT_PORT}")


@shopify_agent.on_event("shutdown")
async def on_shutdown(ctx: Context):
    ctx.logger.info("Shopify Payment Agent shutting down")


if __name__ == "__main__":
    shopify_agent.run()
