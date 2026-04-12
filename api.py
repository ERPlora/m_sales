"""
Sales module REST API — FastAPI router.

JSON endpoints for external consumers (Cloud sync, CLI, webhooks).
Mounted at /api/v1/m/sales/ by ModuleRuntime.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload

from app.core.db.query import HubQuery
from app.core.dependencies import CurrentUser, DbSession, HubId

from .models import (
    PaymentMethod,
    Sale,
    SalesSettings,
)

api_router = APIRouter()


def _q(model, session, hub_id):
    return HubQuery(model, session, hub_id)


@api_router.get("/")
async def list_sales(
    request: Request, db: DbSession, hub_id: HubId,
    q: str = "", status: str = "",
    date_from: str = "", date_to: str = "",
    offset: int = 0, limit: int = Query(default=20, le=100),
):
    """List sales with search and filters."""
    query = _q(Sale, db, hub_id)

    if q:
        query = query.filter(or_(
            Sale.sale_number.ilike(f"%{q}%"),
            Sale.customer_name.ilike(f"%{q}%"),
        ))
    if status:
        query = query.filter(Sale.status == status)
    if date_from:
        query = query.filter(func.date(Sale.created_at) >= date_from)
    if date_to:
        query = query.filter(func.date(Sale.created_at) <= date_to)

    total = await query.count()
    sales = await query.order_by(Sale.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "sales": [{
            "id": str(s.id),
            "sale_number": s.sale_number,
            "status": s.status,
            "subtotal": str(s.subtotal),
            "tax_amount": str(s.tax_amount),
            "discount_amount": str(s.discount_amount),
            "total": str(s.total),
            "payment_method_name": s.payment_method_name,
            "customer_name": s.customer_name,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        } for s in sales],
        "total": total,
    }


@api_router.get("/{sale_id}")
async def get_sale(
    sale_id: uuid.UUID, request: Request, db: DbSession, hub_id: HubId,
):
    """Get sale details with items."""
    sale = await _q(Sale, db, hub_id).options(
        selectinload(Sale.items),
        selectinload(Sale.payment_method_rel),
    ).get(sale_id)
    if sale is None:
        return JSONResponse({"error": "Sale not found"}, status_code=404)

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
        "payment_method_name": sale.payment_method_name,
        "amount_tendered": str(sale.amount_tendered),
        "change_due": str(sale.change_due),
        "customer_name": sale.customer_name,
        "customer_id": str(sale.customer_id) if sale.customer_id else None,
        "employee_id": str(sale.employee_id) if sale.employee_id else None,
        "notes": sale.notes,
        "items": [{
            "id": str(i.id),
            "product_name": i.product_name,
            "product_sku": i.product_sku,
            "is_service": i.is_service,
            "quantity": str(i.quantity),
            "unit_price": str(i.unit_price),
            "discount_percent": str(i.discount_percent),
            "tax_rate": str(i.tax_rate),
            "net_amount": str(i.net_amount),
            "tax_amount": str(i.tax_amount),
            "line_total": str(i.line_total),
        } for i in sale.items],
        "created_at": sale.created_at.isoformat() if sale.created_at else None,
    }


@api_router.post("/{sale_id}/void")
async def void_sale(
    sale_id: uuid.UUID, request: Request,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Void a sale."""
    sale = await _q(Sale, db, hub_id).get(sale_id)
    if sale is None:
        return JSONResponse({"error": "Sale not found"}, status_code=404)
    if sale.status == "voided":
        return JSONResponse({"error": "Sale is already voided"}, status_code=400)

    # Fiscal lock: cannot void a sale that has an active invoice linked.
    from modules.sales.services.sale_void_guard import (
        SaleCannotBeVoidedError,
        ensure_voidable,
    )
    try:
        await ensure_voidable(db, hub_id, sale)
    except SaleCannotBeVoidedError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)

    sale.status = "voided"
    await db.flush()
    return {"id": str(sale.id), "status": "voided"}


@api_router.get("/payment-methods/")
async def list_payment_methods(
    request: Request, db: DbSession, hub_id: HubId,
):
    """List payment methods."""
    pms = await _q(PaymentMethod, db, hub_id).order_by(
        PaymentMethod.sort_order
    ).all()
    return {
        "payment_methods": [{
            "id": str(pm.id),
            "name": pm.name,
            "type": pm.type,
            "icon": pm.icon,
            "is_active": pm.is_active,
            "sort_order": pm.sort_order,
            "opens_cash_drawer": pm.opens_cash_drawer,
            "requires_change": pm.requires_change,
        } for pm in pms],
    }


@api_router.get("/settings/")
async def get_settings(
    request: Request, db: DbSession, hub_id: HubId,
):
    """Get sales settings."""
    settings = await _q(SalesSettings, db, hub_id).first()
    if settings is None:
        return JSONResponse({"error": "Settings not found"}, status_code=404)

    return {
        "allow_cash": settings.allow_cash,
        "allow_card": settings.allow_card,
        "allow_transfer": settings.allow_transfer,
        "sync_products": settings.sync_products,
        "sync_services": settings.sync_services,
        "require_customer": settings.require_customer,
        "allow_discounts": settings.allow_discounts,
        "enable_parked_tickets": settings.enable_parked_tickets,
        "default_tax_included": settings.default_tax_included,
        "ticket_expiry_hours": settings.ticket_expiry_hours,
    }
