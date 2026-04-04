"""
Sales module slot registrations.

Defines slots that OTHER modules can fill (e.g. pos toolbar, pos modals).
The sales module itself is the "host" for POS extension points.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.slots import SlotRegistry

MODULE_ID = "sales"


def register_slots(slots: SlotRegistry, module_id: str) -> None:
    """
    Register slot definitions owned by the sales module.

    Other modules (customers, loyalty, etc.) register content INTO these slots.
    The sales module declares the extension points.

    Called by ModuleRuntime during module load.
    """
    # Declare slots that the POS template renders with {{ render_slot(...) }}
    # Other modules fill these via their own slots.py
    # The sales module doesn't fill its own slots — it owns them.
