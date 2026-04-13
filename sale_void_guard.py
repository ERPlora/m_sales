"""Guard enforcing that a Sale cannot be voided once it has been invoiced.

The canonical link between Sale and Invoice is via
``Invoice.source_type == 'sale' AND Invoice.source_id == sale.id``.
Only invoices in an "active" fiscal status (issued, paid) block voiding;
draft/cancelled invoices do not.

Called from the 3 void entry points (AI tool, HTMX route, REST API) so the
rule is enforced uniformly. A cascade flow (void + auto-issue rectification)
is handled separately in sale_service.void_sale (task F1.B).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from modules.sales.models import Sale


# Invoice statuses that BLOCK voiding the linked sale.
# Keep in sync with modules.invoice.models.INVOICE_STATUS_CHOICES.
# Note: "sent" is not a valid Invoice status — only "issued" and "paid" block.
BLOCKING_INVOICE_STATUSES: frozenset[str] = frozenset({"issued", "paid"})


@dataclass(slots=True)
class ActiveInvoiceRef:
    invoice_id: uuid.UUID
    invoice_number: str  # display label: "{series}/{number}"
    status: str


class SaleCannotBeVoidedError(Exception):
    """Raised when a sale has an active invoice linked and cannot be voided."""

    def __init__(self, sale_number: str, invoice: ActiveInvoiceRef) -> None:
        self.sale_number = sale_number
        self.invoice = invoice
        super().__init__(
            f"Cannot void sale #{sale_number}: invoice #{invoice.invoice_number} "
            f"(status={invoice.status}) is active. Issue a rectification invoice first."
        )


async def find_active_invoice_for_sale(
    session: AsyncSession, hub_id: uuid.UUID, sale_id: uuid.UUID,
) -> ActiveInvoiceRef | None:
    """Return the active invoice linked to a sale, or None.

    Imports the Invoice model lazily so the sales module does not hard-depend
    on the invoice module: when ``invoice`` is not installed the check is a
    no-op (the platform cannot have issued an invoice in that case anyway).
    """
    try:
        from modules.invoice.models import Invoice  # lazy import by design
    except ImportError:
        return None

    stmt = (
        select(Invoice.id, Invoice.series, Invoice.number, Invoice.status)
        .where(
            Invoice.hub_id == hub_id,
            Invoice.source_type == "sale",
            Invoice.source_id == sale_id,
            Invoice.status.in_(BLOCKING_INVOICE_STATUSES),
        )
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        return None
    inv_id, series, number, status = row
    invoice_number = f"{series}/{number}" if series else number
    return ActiveInvoiceRef(invoice_id=inv_id, invoice_number=invoice_number, status=status)


async def ensure_voidable(
    session: AsyncSession, hub_id: uuid.UUID, sale: Sale,
) -> None:
    """Raise SaleCannotBeVoidedError if ``sale`` has an active invoice linked.

    Additional preconditions (status guards) must be checked by the caller
    (already voided / refunded / draft). This function only enforces the
    fiscal lock between Sale and Invoice.
    """
    active = await find_active_invoice_for_sale(session, hub_id, sale.id)
    if active is not None:
        raise SaleCannotBeVoidedError(sale_number=sale.sale_number, invoice=active)
