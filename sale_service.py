"""
Sale service — shared business logic for creating Sales.

Used by:
  - sales/routes.py  (POST /pos/api/complete-sale)
  - pos/routes.py    (POS kiosk complete-sale)
  - orders/...       (B2B flow, future)

Callers must provide an open DB session. This service does NOT commit — the
caller decides the transaction boundary. After commit, caller should emit
sale.completed via sales.events.emit_sale_completed.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from runtime.models.queryset import HubQuery

from sales.models import (
    PaymentMethod,
    Sale,
    SaleItem,
    SalesSettings,
    generate_sale_number,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _q(model: Any, session: AsyncSession, hub_id: UUID) -> HubQuery:
    return HubQuery(model, session, hub_id)


class SaleService:
    """Stateless helpers to create Sales from any source module."""

    @staticmethod
    async def create_sale(
        *,
        db: AsyncSession,
        hub_id: UUID,
        items: list[Any],
        channel: str = "",
        source_module: str = "",
        status: str = "completed",
        employee: Any = None,
        customer: Any = None,
        customer_name: str = "",
        payment_method: PaymentMethod | None = None,
        amount_tendered: Decimal | float | int = 0,
        notes: str = "",
        request: Any = None,
    ) -> Sale:
        """
        Create a Sale + SaleItems with tax calculation and optional stock update.

        Items: list of dicts OR pydantic objects exposing:
          product_id, product_name, product_sku, is_service, quantity,
          price, discount, tax_rate, tax_class_name.

        Returns the flushed Sale (not committed).
        """
        settings = await _q(SalesSettings, db, hub_id).first()
        tax_included = settings.default_tax_included if settings else True

        sale_number = await generate_sale_number(db, hub_id)

        sale = Sale(
            hub_id=hub_id,
            sale_number=sale_number,
            employee_id=getattr(employee, "id", None),
            payment_method_id=getattr(payment_method, "id", None),
            payment_method_name=getattr(payment_method, "name", "") or "",
            amount_tendered=Decimal(str(amount_tendered)),
            customer_id=getattr(customer, "id", None),
            customer_name=customer_name or getattr(customer, "name", "") or "",
            notes=notes,
            source_module=source_module,
            channel=channel,
            status=status,
        )
        db.add(sale)
        await db.flush()

        def _getattr(item: Any, name: str, default: Any = None) -> Any:
            if isinstance(item, dict):
                return item.get(name, default)
            return getattr(item, name, default)

        sale_items: list[SaleItem] = []
        for item in items:
            def _g(name: str, default: Any = None, _item: Any = item) -> Any:
                return _getattr(_item, name, default)

            raw_product_id = _g("product_id")
            product_id = None
            product_name = _g("product_name", "") or ""
            product_sku = _g("product_sku", "") or ""
            is_service = bool(_g("is_service", False))
            quantity = Decimal(str(_g("quantity", 0)))

            # Resolve product + stock adjustment
            if raw_product_id:
                try:
                    from inventory.models import Product

                    product_uuid = raw_product_id if isinstance(raw_product_id, UUID) else UUID(str(raw_product_id))
                    product = await _q(Product, db, hub_id).get(product_uuid)
                    if product is not None:
                        product_id = product.id
                        product_name = product_name or product.name
                        product_sku = product_sku or getattr(product, "sku", "") or ""
                        if not is_service and status == "completed":
                            product.stock -= int(quantity)
                except ImportError:
                    pass
                except Exception:
                    logger.exception("Failed to resolve product %s", raw_product_id)

            sale_item = SaleItem(
                hub_id=hub_id,
                sale_id=sale.id,
                product_id=product_id,
                product_name=product_name,
                product_sku=product_sku,
                is_service=is_service,
                quantity=quantity,
                unit_price=Decimal(str(_g("price", 0))),
                discount_percent=Decimal(str(_g("discount", 0))),
                tax_rate=Decimal(str(_g("tax_rate", 0))),
                tax_class_name=_g("tax_class_name", "") or "",
            )
            sale_item.calculate_line_totals(tax_included=tax_included)
            db.add(sale_item)
            sale_items.append(sale_item)

        await db.flush()

        sale.calculate_totals(items=sale_items)
        sale.calculate_change(Decimal(str(amount_tendered)))
        return sale


# ---------------------------------------------------------------------------
# Void sale — module-level function (not a SaleService method)
# ---------------------------------------------------------------------------

async def void_sale(
    session: AsyncSession,
    hub_id: UUID,
    sale: Sale,
    *,
    reason: str = "",
    cascade_invoice: bool = False,
    bus: Any = None,
) -> dict:
    """Void a sale, optionally cascading into invoice rectification.

    If cascade_invoice=True and there is an active invoice linked to the sale,
    the function delegates to InvoiceService.rectify() (which creates an R1
    invoice with negated amounts and marks the original as 'cancelled'), then
    emits ``invoice.cancelled`` so verifactu can produce the 'anulacion' record.

    If cascade_invoice=False (default) and there is an active invoice, raises
    SaleCannotBeVoidedError.

    Parameters
    ----------
    session:
        Open AsyncSession — caller controls the transaction boundary.
    hub_id:
        UUID of the current hub.
    sale:
        Sale ORM instance to void.
    reason:
        Human-readable reason stored in sale.notes and invoice description.
    cascade_invoice:
        When True, auto-issue a rectifying invoice instead of blocking.
    bus:
        AsyncEventBus instance.  When provided, sale.voided is emitted after
        the void.  Pass None to skip event emission (e.g. in tests).

    Returns
    -------
    dict
        ``{sale_number, status, cascaded, rectification_id}``

    Raises
    ------
    SaleCannotBeVoidedError
        If an active invoice exists and cascade_invoice is False.
    """
    from sales.sale_void_guard import (
        SaleCannotBeVoidedError,
        find_active_invoice_for_sale,
    )

    active_invoice = await find_active_invoice_for_sale(session, hub_id, sale.id)
    rect_invoice_id: str | None = None
    cascaded = False

    if active_invoice is not None:
        if not cascade_invoice:
            from sales.sale_void_guard import SaleCannotBeVoidedError
            raise SaleCannotBeVoidedError(sale.sale_number, active_invoice)

        # Delegate rectification to InvoiceService (already has full R1 logic).
        try:
            from invoice.invoice_service import InvoiceService
        except ImportError as exc:
            raise RuntimeError(
                "invoice module is required for cascade void but is not installed"
            ) from exc

        svc = InvoiceService(session, hub_id)
        rect_invoice = await svc.rectify(
            active_invoice.invoice_id,
            reason=reason or f"Void of sale #{sale.sale_number}",
        )
        cascaded = True
        rect_invoice_id = str(rect_invoice.id)

        # Emit invoice.cancelled for verifactu (original invoice id, not rect).
        if bus is not None:
            try:
                from invoice.events import emit_invoice_cancelled, emit_invoice_rectified
                await emit_invoice_cancelled(
                    bus,
                    invoice_id=str(active_invoice.invoice_id),
                    hub_id=str(hub_id),
                )
                await emit_invoice_rectified(
                    bus,
                    original_invoice_id=str(active_invoice.invoice_id),
                    rectifying_invoice_id=rect_invoice_id,
                    hub_id=str(hub_id),
                )
            except Exception:
                logger.exception(
                    "Failed to emit invoice events for cascade void of sale %s — "
                    "rectification was committed, fiscal events may be delayed",
                    sale.sale_number,
                )

    # Mark sale as voided with traceability note.
    sale.status = "voided"
    suffix = f"[VOIDED] {reason}".strip() if reason else "[VOIDED]"
    sale.notes = f"{sale.notes}\n{suffix}".strip() if sale.notes else suffix
    await session.flush()

    # Emit sale.voided for audit / downstream consumers.
    if bus is not None:
        try:
            from sales.events import emit_sale_voided
            await emit_sale_voided(
                bus,
                sale_id=str(sale.id),
                hub_id=str(hub_id),
                sale_number=sale.sale_number or "",
            )
        except Exception:
            logger.exception("Failed to emit sale.voided for sale %s", sale.sale_number)

    return {
        "sale_number": sale.sale_number,
        "status": sale.status,
        "cascaded": cascaded,
        "rectification_id": rect_invoice_id,
    }
