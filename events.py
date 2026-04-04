"""
Sales module event subscriptions.

Registers handlers on the AsyncEventBus during module load.
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
