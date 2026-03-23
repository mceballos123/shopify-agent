from pydantic import BaseModel
from uagents import Model


class CartLineInput(BaseModel):
    merchandise_id: str
    quantity: int = 1
    attributes: list[dict] | None = None


class CartCreateRequest(BaseModel):
    lines: list[CartLineInput]
    buyer_identity: dict | None = None
    attributes: list[dict] | None = None
    note: str | None = None


class CartLinesAddRequest(BaseModel):
    cart_id: str
    lines: list[CartLineInput]


class CartLineUpdateInput(BaseModel):
    id: str
    quantity: int | None = None
    merchandise_id: str | None = None
    attributes: list[dict] | None = None


class CartLinesUpdateRequest(BaseModel):
    cart_id: str
    lines: list[CartLineUpdateInput]


class CartLinesRemoveRequest(BaseModel):
    cart_id: str
    line_ids: list[str]


class CartBuyerIdentityRequest(BaseModel):
    cart_id: str
    buyer_identity: dict


class CartAttributesRequest(BaseModel):
    cart_id: str
    attributes: list[dict]


# ── Agent message models ────────────────────────────────────────────────────

class ShopifyRequest(Model):
    """Inbound request from another agent."""
    action: str
    cart_id: str = ""
    lines: list = []
    line_ids: list = []
    buyer_identity: dict = {}
    attributes: list = []
    note: str = ""


class ShopifyResponse(Model):
    """Outbound response back to the requesting agent."""
    success: bool
    action: str
    data: dict = {}
    error: str = ""
    redirect_url: str = ""
