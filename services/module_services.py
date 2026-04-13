"""
Sales module services — ModuleService pattern.

Services: SalesQueryService, PaymentMethodService.

Note: sale creation logic lives in sale_service.py (SaleService).
      Void guard logic lives in sale_void_guard.py.
      This file covers AI-facing query and action methods.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import or_

from app.core.db.repository import serialize, serialize_list
from app.core.db.transactions import atomic
from app.modules.services import ModuleService, action

from sales.models import PaymentMethod, Sale, SaleItem


# ============================================================================
# Sales Query Service
# ============================================================================

class SalesQueryService(ModuleService):
    """Sales queries and actions (list, detail, stats, void)."""

    @action(permission="view_sale")
    async def list_sales(
        self,
        *,
        status: str = "",
        date_from: str = "",
        date_to: str = "",
        search: str = "",
        limit: int = 20,
    ):
        """List sales with optional filters."""
        q = self.q(Sale)

        if status:
            q = q.filter(Sale.status == status)
        if date_from:
            q = q.filter(Sale.created_at >= datetime.fromisoformat(date_from))
        if date_to:
            dt_to = datetime.fromisoformat(date_to)
            q = q.filter(Sale.created_at < dt_to + timedelta(days=1))
        if search:
            q = q.filter(or_(
                Sale.sale_number.ilike(f"%{search}%"),
                Sale.customer_name.ilike(f"%{search}%"),
            ))

        total = await q.count()
        sales = await q.order_by(Sale.created_at.desc()).limit(limit).all()

        return {
            "sales": [
                {
                    "id": str(s.id),
                    "sale_number": s.sale_number,
                    "status": s.status,
                    "total": str(s.total),
                    "customer_name": s.customer_name or "",
                    "payment_method": s.payment_method_name or "",
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in sales
            ],
            "total": total,
        }

    @action(permission="view_sale")
    async def get_detail(self, *, sale_id: str):
        """Get full sale details including line items and tax breakdown."""
        sale = await self.q(Sale).get(uuid.UUID(sale_id))
        if sale is None:
            return {"error": "Sale not found"}

        items = await self.q(SaleItem).filter(
            SaleItem.sale_id == sale.id,
        ).all()

        return {
            "id": str(sale.id),
            "sale_number": sale.sale_number,
            "status": sale.status,
            "subtotal": str(sale.subtotal),
            "tax_amount": str(sale.tax_amount),
            "tax_breakdown": sale.tax_breakdown,
            "discount_amount": str(sale.discount_amount),
            "discount_percent": str(sale.discount_percent),
            "total": str(sale.total),
            "payment_method": sale.payment_method_name or "",
            "amount_tendered": str(sale.amount_tendered),
            "change_due": str(sale.change_due),
            "customer_name": sale.customer_name or "",
            "notes": sale.notes or "",
            "created_at": sale.created_at.isoformat() if sale.created_at else None,
            "items": [
                {
                    "id": str(item.id),
                    "product_name": item.product_name,
                    "product_sku": item.product_sku,
                    "is_service": item.is_service,
                    "quantity": str(item.quantity),
                    "unit_price": str(item.unit_price),
                    "discount_percent": str(item.discount_percent),
                    "tax_rate": str(item.tax_rate),
                    "net_amount": str(item.net_amount),
                    "tax_amount": str(item.tax_amount),
                    "line_total": str(item.line_total),
                    "notes": item.notes or "",
                }
                for item in items
            ],
        }

    @action(permission="view_sale")
    async def get_stats(self, *, date_from: str = "", date_to: str = ""):
        """Get sales statistics: revenue, count, average ticket for a period."""
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        dt_from = datetime.fromisoformat(date_from) if date_from else today
        dt_to = datetime.fromisoformat(date_to) if date_to else today
        dt_to_end = dt_to + timedelta(days=1)

        q = self.q(Sale).filter(
            Sale.status == "completed",
            Sale.created_at >= dt_from,
            Sale.created_at < dt_to_end,
        )

        sales = await q.all()
        total_revenue = sum(s.total for s in sales)
        count = len(sales)
        avg_ticket = (total_revenue / count) if count > 0 else Decimal("0.00")

        return {
            "period": {
                "from": dt_from.date().isoformat(),
                "to": dt_to.date().isoformat(),
            },
            "total_revenue": str(total_revenue),
            "sale_count": count,
            "average_ticket": str(avg_ticket.quantize(Decimal("0.01"))),
        }

    @action(permission="void_sale", mutates=True)
    async def void_sale(self, *, sale_id: str, reason: str = ""):
        """Void a completed sale (checks fiscal locks)."""
        sale = await self.q(Sale).get(uuid.UUID(sale_id))
        if sale is None:
            return {"error": "Sale not found"}

        if sale.status == "voided":
            return {"error": "Sale is already voided"}
        if sale.status == "refunded":
            return {"error": "Cannot void a refunded sale"}
        if sale.status == "draft":
            return {"error": "Cannot void a draft sale — delete it instead"}

        from modules.sales.services.sale_void_guard import (
            SaleCannotBeVoidedError,
            ensure_voidable,
        )
        try:
            await ensure_voidable(self.db, self.hub_id, sale)
        except SaleCannotBeVoidedError as exc:
            return {"error": str(exc)}

        async with atomic(self.db):
            sale.status = "voided"
            sale.notes = f"{sale.notes}\n[VOIDED] {reason}".strip()
            await self.db.flush()

        return {
            "sale_number": sale.sale_number,
            "status": sale.status,
            "voided": True,
        }


# ============================================================================
# Payment Method Service
# ============================================================================

class PaymentMethodService(ModuleService):
    """Payment method configuration."""

    @action(permission="view_sale")
    async def list_payment_methods(self, *, active_only: bool = False):
        """List configured payment methods."""
        q = self.q(PaymentMethod)
        if active_only:
            q = q.filter(PaymentMethod.is_active == True)  # noqa: E712
        methods = await q.order_by(PaymentMethod.sort_order, PaymentMethod.name).all()

        return {
            "payment_methods": serialize_list(
                methods,
                fields=[
                    "id", "name", "type", "icon", "is_active",
                    "opens_cash_drawer", "requires_change", "sort_order",
                ],
            ),
        }

    @action(permission="manage_settings", mutates=True)
    async def create_payment_method(
        self,
        *,
        name: str,
        type: str,
        icon: str = "",
        opens_cash_drawer: bool = False,
        requires_change: bool = False,
        sort_order: int = 0,
    ):
        """Create a new payment method."""
        valid_types = ("cash", "card", "transfer", "other")
        if type not in valid_types:
            return {"error": f"Invalid payment type '{type}'. Must be one of: {valid_types}"}

        async with atomic(self.db) as session:
            method = PaymentMethod(
                hub_id=self.hub_id,
                name=name,
                type=type,
                icon=icon,
                opens_cash_drawer=opens_cash_drawer,
                requires_change=requires_change,
                sort_order=sort_order,
            )
            session.add(method)
            await session.flush()

        return {
            "id": str(method.id),
            "name": method.name,
            "type": method.type,
            "created": True,
        }
