"""
Sales module hook registrations.

Registers actions and filters on the HookRegistry during module load.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.hooks.registry import HookRegistry

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


async def _on_sale_completed_action(
    sale=None,
    session=None,
    **kwargs,
) -> None:
    """
    Default action when a sale is completed.
    Other modules can add_action('sale.completed', ...) to extend.
    """
