"""
In-memory payment session store.

Keyed by source_identifier. Persists session state across HTTP requests
within a single process lifetime so that page refreshes don't create
duplicate payment sessions.

Production deployments should swap _store for Redis or a DB-backed store.
"""
import threading
from dataclasses import dataclass
from enum import Enum


class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PaymentRecord:
    source_identifier: str
    idempotency_key: str
    checkout_url: str
    token: str
    status: PaymentStatus = PaymentStatus.PENDING


_store: dict[str, PaymentRecord] = {}
_lock = threading.Lock()


def save_session(record: PaymentRecord) -> None:
    with _lock:
        _store[record.source_identifier] = record


def get_session(source_identifier: str) -> PaymentRecord | None:
    with _lock:
        return _store.get(source_identifier)


def update_status(source_identifier: str, status: PaymentStatus) -> bool:
    with _lock:
        if source_identifier in _store:
            _store[source_identifier].status = status
            return True
        return False
