"""
Sales module event subscriptions and emissions.

Registers handlers on the AsyncEventBus during module load.
Other modules (invoice, verifactu) listen to sales.* events.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.events.bus import AsyncEventBus

logger = logging.getLogger(__name__)

MODULE_ID = "sales"


async def register_events(bus: AsyncEventBus, module_id: str) -> None:
    """
    Register event handlers for the sales module.

    Called by ModuleRuntime during module load.
    """

    # Listen for inventory stock changes (optional integration)
    await bus.subscribe(
            "inventory.stock_updated",
            _on_stock_updated,
            module_id=module_id,
        )


async def _on_stock_updated(
    event: str,
    sender: object = None,
    product: object = None,
    **kwargs: object,
) -> None:
    """
    When inventory stock is updated, log for traceability.
    Sales module mostly *causes* stock changes, but can also react.
    """
    if product is None:
        return

    logger.debug(
        "Stock updated for product %s (sales module notified)",
        getattr(product, "id", "?"),
    )


# ---------------------------------------------------------------------------
# Emit helpers — called by routes after DB write
# ---------------------------------------------------------------------------


async def emit_sale_completed(
    bus: AsyncEventBus,
    *,
    sale_id: str,
    hub_id: str,
    total: float,
    subtotal: float,
    tax_amount: float,
    items_count: int,
    customer_id: str | None = None,
    customer_name: str = "",
    sale_number: str = "",
) -> None:
    """Emit sales.completed — invoice module subscribes to auto-create Invoice F2."""
    await bus.emit(
        "sales.completed",
        sender=MODULE_ID,
        sale_id=sale_id,
        hub_id=hub_id,
        total=total,
        subtotal=subtotal,
        tax_amount=tax_amount,
        items_count=items_count,
        customer_id=customer_id,
        customer_name=customer_name,
        sale_number=sale_number,
    )
    logger.info("Emitted sales.completed for sale %s (hub %s)", sale_id, hub_id)


async def emit_sale_voided(
    bus: AsyncEventBus,
    *,
    sale_id: str,
    hub_id: str,
    sale_number: str = "",
) -> None:
    """Emit sales.voided — for future consumers (analytics, stock reconciliation, etc.)."""
    await bus.emit(
        "sales.voided",
        sender=MODULE_ID,
        sale_id=sale_id,
        hub_id=hub_id,
        sale_number=sale_number,
    )
    logger.info("Emitted sales.voided for sale %s (hub %s)", sale_id, hub_id)


async def emit_sale_refunded(
    bus: AsyncEventBus,
    *,
    sale_id: str,
    hub_id: str,
    refund_amount: float = 0.0,
    sale_number: str = "",
) -> None:
    """Emit sales.refunded — for future consumers (invoice rectification, analytics, etc.)."""
    await bus.emit(
        "sales.refunded",
        sender=MODULE_ID,
        sale_id=sale_id,
        hub_id=hub_id,
        refund_amount=refund_amount,
        sale_number=sale_number,
    )
    logger.info("Emitted sales.refunded for sale %s (hub %s)", sale_id, hub_id)
