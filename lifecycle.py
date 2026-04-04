"""
Sales module lifecycle hooks.

Called by ModuleRuntime during install/activate/deactivate/uninstall/upgrade.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def on_install(session: AsyncSession, hub_id: UUID) -> None:
    """Called after module installation + migration. Seed default payment methods."""
    from .models import PaymentMethod, SalesSettings

    # Create default settings
    settings = SalesSettings(hub_id=hub_id)
    session.add(settings)

    # Create default payment methods
    defaults = [
        {"name": "Cash", "type": "cash", "icon": "cash-outline", "sort_order": 0, "opens_cash_drawer": True, "requires_change": True},
        {"name": "Card", "type": "card", "icon": "card-outline", "sort_order": 1, "opens_cash_drawer": False, "requires_change": False},
        {"name": "Bank Transfer", "type": "transfer", "icon": "swap-horizontal-outline", "sort_order": 2, "opens_cash_drawer": False, "requires_change": False},
    ]
    for pm_data in defaults:
        pm = PaymentMethod(hub_id=hub_id, **pm_data)
        session.add(pm)

    await session.flush()
    logger.info("Sales module installed for hub %s — default settings and payment methods created", hub_id)


async def on_activate(session: AsyncSession, hub_id: UUID) -> None:
    """Called when module is activated."""
    logger.info("Sales module activated for hub %s", hub_id)


async def on_deactivate(session: AsyncSession, hub_id: UUID) -> None:
    """Called when module is deactivated."""
    logger.info("Sales module deactivated for hub %s", hub_id)


async def on_uninstall(session: AsyncSession, hub_id: UUID) -> None:
    """Called before module uninstall."""
    logger.info("Sales module uninstalled for hub %s", hub_id)


async def on_upgrade(session: AsyncSession, hub_id: UUID, from_version: str, to_version: str) -> None:
    """Called when the module is updated. Run data migrations between versions."""
    logger.info(
        "Sales module upgraded from %s to %s for hub %s",
        from_version, to_version, hub_id,
    )
