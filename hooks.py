"""
Sales module hook registrations.

Registers actions and filters on the HookRegistry during module load.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.signals.hooks import HookRegistry

logger = logging.getLogger(__name__)

MODULE_ID = "sales"


def register_hooks(hooks: HookRegistry, module_id: str) -> None:
    """
    Register hooks for the sales module.

    Called by ModuleRuntime during module load.
    """
    # Action: after sale completed — other modules can subscribe
    hooks.add_action(
        "sale.completed",
        _on_sale_completed_action,
        priority=10,
        module_id=module_id,
    )


def _needs_kitchen(item: object) -> bool:
    """
    Return True if a SaleItem needs kitchen preparation.

    Checks the item's product for ``needs_preparation=True`` (flag on the
    inventory Product model, if present) OR for membership in a category
    that is marked as a kitchen category (``kitchen_category=True`` on the
    inventory Category model, if present).

    Both fields are optional — they may not exist on the current inventory
    version, so we use getattr with a safe default.
    """
    # Direct flag on SaleItem or related product snapshot
    if getattr(item, "needs_preparation", False):
        return True

    # Try to resolve via the product object if it was eagerly loaded
    product = getattr(item, "product", None)
    if product is not None:
        if getattr(product, "needs_preparation", False):
            return True
        for cat in getattr(product, "categories", []):
            if getattr(cat, "kitchen_category", False):
                return True

    return False


async def _on_sale_completed_action(
    sale=None,
    session=None,
    bus=None,
    **kwargs,
) -> None:
    """
    Emit ``kitchen.order_required`` when a completed sale contains items that
    need kitchen preparation.

    Other modules (commands) subscribe to this event to create kitchen orders.
    Skipped silently when:
      - sale is None
      - sale.status != 'completed'
      - no items require kitchen preparation
    """
    if sale is None:
        return

    if getattr(sale, "status", None) != "completed":
        return

    items = getattr(sale, "items", []) or []
    kitchen_items = [
        {
            "product_id": str(i.product_id) if getattr(i, "product_id", None) else None,
            "quantity": float(i.quantity),
            "notes": getattr(i, "notes", "") or "",
        }
        for i in items
        if _needs_kitchen(i)
    ]

    if not kitchen_items:
        logger.debug(
            "sale.completed hook: no kitchen items in sale %s — skipping emit",
            getattr(sale, "id", "?"),
        )
        return

    if bus is None:
        logger.warning(
            "sale.completed hook: bus not available for sale %s — cannot emit kitchen event",
            getattr(sale, "id", "?"),
        )
        return

    payload = {
        "hub_id": str(sale.hub_id),
        "sale_id": str(sale.id),
        "table_id": str(sale.table_id) if getattr(sale, "table_id", None) else None,
        "items": kitchen_items,
        "channel": getattr(sale, "channel", "") or "pos",
    }

    await bus.emit(
        "kitchen.order_required",
        sender=MODULE_ID,
        **payload,
    )
    logger.info(
        "Emitted kitchen.order_required for sale %s (%d kitchen items)",
        sale.id,
        len(kitchen_items),
    )
