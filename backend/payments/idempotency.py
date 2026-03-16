import uuid


def generate_idempotency_key() -> str:
    """Generate a unique idempotency key (UUID v4) for payment submission."""
    return str(uuid.uuid4())


def generate_source_identifier(prefix: str = "order") -> str:
    """Generate a unique source identifier for cart/order tracking."""
    return f"{prefix}-{uuid.uuid4()}"
