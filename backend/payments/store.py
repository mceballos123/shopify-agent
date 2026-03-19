"""
In-memory cart/order store.

Keyed by cart_id. Tracks cart state and order status across HTTP requests
within a single process lifetime.

Production deployments should swap _store for Redis or a DB-backed store.
"""
import threading
from dataclasses import dataclass, field
from enum import Enum


class OrderStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CartRecord:
    cart_id: str
    checkout_url: str
    status: OrderStatus = OrderStatus.ACTIVE
    order_id: str | None = None
    source_identifier: str | None = None


_store: dict[str, CartRecord] = {}
_lock = threading.Lock()


def save_cart(record: CartRecord) -> None:
    with _lock:
        _store[record.cart_id] = record


def get_cart(cart_id: str) -> CartRecord | None:
    with _lock:
        return _store.get(cart_id)


def update_status(cart_id: str, status: OrderStatus, order_id: str | None = None) -> bool:
    with _lock:
        if cart_id in _store:
            _store[cart_id].status = status
            if order_id:
                _store[cart_id].order_id = order_id
            return True
        return False


def find_cart_by_source(source_identifier: str) -> CartRecord | None:
    """Look up a cart by its source_identifier (stored as a cart attribute)."""
    with _lock:
        for record in _store.values():
            if record.source_identifier == source_identifier:
                return record
        return None
