"""
Shopify Cart Agent — single entry point.

Run:
    cd backend
    python -m agent.shopify_agent

Starts the FastAPI server (HTTP routes, UI) and the uAgent
(ASI1 Chat protocol with Gemini + Composio) in a single process.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from uagents import Agent, Context
from agent.chat_protocol import chat_protocol
from server import app  # FastAPI app with all HTTP routes

load_dotenv()

AGENT_SEED = os.getenv("SHOPIFY_AGENT_SEED", "shopify-agent-default-seed")
AGENT_PORT = int(os.getenv("SHOPIFY_AGENT_PORT", "8001"))

shopify_agent = Agent(
    name="ShopifyCartAgent",
    seed=AGENT_SEED,
    port=AGENT_PORT,
    mailbox=True,
)

shopify_agent.include(chat_protocol, publish_manifest=True)


@shopify_agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(
        f"Shopify Cart Agent started — "
        f"name={ctx.agent.name}  address={ctx.agent.address}"
    )
    ctx.logger.info(f"Agent address: {ctx.agent.address}")
    ctx.logger.info(f"Agent listening on port {AGENT_PORT}")


@shopify_agent.on_event("shutdown")
async def on_shutdown(ctx: Context):
    ctx.logger.info("Shopify Cart Agent shutting down")


def main():
    """Run the uAgent (with its event loop) and mount FastAPI on it."""
    shopify_agent.run()


if __name__ == "__main__":
    main()
