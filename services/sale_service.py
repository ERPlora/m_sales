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

from app.core.db.query import HubQuery

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
