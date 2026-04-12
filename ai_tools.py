"""
AI tools for the Sales module.

Uses @register_tool + AssistantTool class pattern.
All tools are async and use HubQuery for DB access.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import or_

from app.ai.registry import AssistantTool, register_tool
from app.core.db.query import HubQuery
from app.core.db.transactions import atomic

from .models import PaymentMethod, Sale, SaleItem


def _q(model, session, hub_id):
    return HubQuery(model, session, hub_id)


# ==============================================================================
# SALES — READ-ONLY
# ==============================================================================

@register_tool
class ListSales(AssistantTool):
    name = "list_sales"
    description = (
        "List sales with optional filters by status, date range, customer, or search. "
        "Returns sale number, status, total, customer, date. Read-only."
    )
    module_id = "sales"
    required_permission = "sales.view_sale"
    parameters = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "Filter by status: draft, pending, completed, voided, refunded.",
            },
            "date_from": {
                "type": "string",
                "description": "Start date (ISO format, e.g. '2026-04-01').",
            },
            "date_to": {
                "type": "string",
                "description": "End date (ISO format, e.g. '2026-04-07').",
            },
            "search": {
                "type": "string",
                "description": "Search by sale number or customer name.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results (default 20).",
            },
        },
        "required": [],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id
        q = _q(Sale, db, hub_id)

        if args.get("status"):
            q = q.filter(Sale.status == args["status"])
        if args.get("date_from"):
            q = q.filter(Sale.created_at >= datetime.fromisoformat(args["date_from"]))
        if args.get("date_to"):
            date_to = datetime.fromisoformat(args["date_to"])
            # Include the entire end day
            q = q.filter(Sale.created_at < date_to + timedelta(days=1))
        if args.get("search"):
            s = args["search"]
            q = q.filter(or_(
                Sale.sale_number.ilike(f"%{s}%"),
                Sale.customer_name.ilike(f"%{s}%"),
            ))

        limit = args.get("limit", 20)
        total = await q.count()
        sales = await q.order_by(Sale.created_at.desc()).limit(limit).all()

        return {
            "sales": [{
                "id": str(sale.id),
                "sale_number": sale.sale_number,
                "status": sale.status,
                "total": str(sale.total),
                "customer_name": sale.customer_name or "",
                "payment_method": sale.payment_method_name or "",
                "created_at": sale.created_at.isoformat() if sale.created_at else None,
            } for sale in sales],
            "total": total,
        }


@register_tool
class GetSaleDetail(AssistantTool):
    name = "get_sale_detail"
    description = "Get full details of a sale including all line items, tax breakdown, and payment info."
    module_id = "sales"
    required_permission = "sales.view_sale"
    parameters = {
        "type": "object",
        "properties": {
            "sale_id": {"type": "string", "description": "UUID of the sale."},
        },
        "required": ["sale_id"],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id
        sale = await _q(Sale, db, hub_id).get(uuid.UUID(args["sale_id"]))
        if sale is None:
            return {"error": "Sale not found"}

        items = await _q(SaleItem, db, hub_id).filter(
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
            "items": [{
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
            } for item in items],
        }


@register_tool
class GetSalesStats(AssistantTool):
    name = "get_sales_stats"
    description = (
        "Get sales statistics: revenue, count, average ticket for a period. "
        "Defaults to today. Read-only."
    )
    module_id = "sales"
    required_permission = "sales.view_sale"
    parameters = {
        "type": "object",
        "properties": {
            "date_from": {
                "type": "string",
                "description": "Start date (ISO). Defaults to today.",
            },
            "date_to": {
                "type": "string",
                "description": "End date (ISO). Defaults to today.",
            },
        },
        "required": [],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id

        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        date_from = datetime.fromisoformat(args["date_from"]) if args.get("date_from") else today
        date_to = datetime.fromisoformat(args["date_to"]) if args.get("date_to") else today
        date_to_end = date_to + timedelta(days=1)

        q = _q(Sale, db, hub_id).filter(
            Sale.status == "completed",
            Sale.created_at >= date_from,
            Sale.created_at < date_to_end,
        )

        sales = await q.all()
        total_revenue = sum(s.total for s in sales)
        count = len(sales)
        avg_ticket = (total_revenue / count) if count > 0 else Decimal("0.00")

        return {
            "period": {
                "from": date_from.date().isoformat(),
                "to": date_to.date().isoformat(),
            },
            "total_revenue": str(total_revenue),
            "sale_count": count,
            "average_ticket": str(avg_ticket.quantize(Decimal("0.01"))),
        }


# ==============================================================================
# SALES — ACTIONS
# ==============================================================================

@register_tool
class VoidSale(AssistantTool):
    name = "void_sale"
    description = (
        "Void a completed sale. Cannot void if already voided/refunded, "
        "or if the sale has been invoiced."
    )
    module_id = "sales"
    required_permission = "sales.void_sale"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "sale_id": {"type": "string", "description": "UUID of the sale to void."},
            "reason": {"type": "string", "description": "Reason for voiding the sale."},
        },
        "required": ["sale_id"],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id
        sale = await _q(Sale, db, hub_id).get(uuid.UUID(args["sale_id"]))
        if sale is None:
            return {"error": "Sale not found"}

        if sale.status == "voided":
            return {"error": "Sale is already voided"}
        if sale.status == "refunded":
            return {"error": "Cannot void a refunded sale"}
        if sale.status == "draft":
            return {"error": "Cannot void a draft sale — delete it instead"}

        # Fiscal lock: cannot void a sale that has an active invoice linked.
        from modules.sales.services.sale_void_guard import (
            SaleCannotBeVoidedError,
            ensure_voidable,
        )
        try:
            await ensure_voidable(db, hub_id, sale)
        except SaleCannotBeVoidedError as exc:
            return {"error": str(exc)}

        async with atomic(db):
            sale.status = "voided"
            sale.notes = (
                f"{sale.notes}\n[VOIDED] {args.get('reason', '')}"
            ).strip()
            await db.flush()

        return {
            "sale_number": sale.sale_number,
            "status": sale.status,
            "voided": True,
        }


# ==============================================================================
# PAYMENT METHODS
# ==============================================================================

@register_tool
class ListPaymentMethods(AssistantTool):
    name = "list_payment_methods"
    description = "List configured payment methods. Read-only."
    module_id = "sales"
    required_permission = "sales.view_sale"
    parameters = {
        "type": "object",
        "properties": {
            "active_only": {
                "type": "boolean",
                "description": "If true, return only active methods. Default false.",
            },
        },
        "required": [],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id
        q = _q(PaymentMethod, db, hub_id)
        if args.get("active_only"):
            q = q.filter(PaymentMethod.is_active == True)  # noqa: E712
        methods = await q.order_by(PaymentMethod.sort_order, PaymentMethod.name).all()
        return {
            "payment_methods": [{
                "id": str(m.id),
                "name": m.name,
                "type": m.type,
                "icon": m.icon,
                "is_active": m.is_active,
                "opens_cash_drawer": m.opens_cash_drawer,
                "requires_change": m.requires_change,
                "sort_order": m.sort_order,
            } for m in methods],
        }


@register_tool
class CreatePaymentMethod(AssistantTool):
    name = "create_payment_method"
    description = "Create a new payment method (cash, card, transfer, other)."
    module_id = "sales"
    required_permission = "sales.manage_settings"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Display name (e.g. 'Efectivo', 'Visa')."},
            "type": {
                "type": "string",
                "description": "Payment type: cash, card, transfer, other.",
            },
            "icon": {"type": "string", "description": "Icon name (optional)."},
            "opens_cash_drawer": {
                "type": "boolean",
                "description": "Whether this method opens the cash drawer. Default false.",
            },
            "requires_change": {
                "type": "boolean",
                "description": "Whether change calculation is needed (e.g. cash). Default false.",
            },
            "sort_order": {"type": "integer", "description": "Display order. Default 0."},
        },
        "required": ["name", "type"],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id

        valid_types = ("cash", "card", "transfer", "other")
        if args["type"] not in valid_types:
            return {"error": f"Invalid payment type '{args['type']}'. Must be one of: {valid_types}"}

        async with atomic(db) as session:
            method = PaymentMethod(
                hub_id=hub_id,
                name=args["name"],
                type=args["type"],
                icon=args.get("icon", ""),
                opens_cash_drawer=args.get("opens_cash_drawer", False),
                requires_change=args.get("requires_change", False),
                sort_order=args.get("sort_order", 0),
            )
            session.add(method)
            await session.flush()

        return {"id": str(method.id), "name": method.name, "type": method.type, "created": True}
