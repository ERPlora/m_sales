"""
Sales module HTMX views — FastAPI router.

Replaces Django views.py + urls.py. Uses @htmx_view decorator.
Mounted at /m/sales/ by ModuleRuntime.
"""

from __future__ import annotations

import calendar
import logging
import uuid
from datetime import datetime, timedelta, UTC
from decimal import Decimal

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload

from app.core.db.query import HubQuery
from app.core.db.transactions import atomic
from app.core.dependencies import CurrentUser, DbSession, HubId
from app.core.htmx import htmx_view

from .models import (
    ActiveCart,
    ParkedTicket,
    PaymentMethod,
    Sale,
    SaleItem,
    SalesSettings,
    generate_sale_number,
    generate_ticket_number,
)
from .schemas import (
    CompleteSaleRequest,
    PaymentMethodCreate,
    SalesSettingsUpdate,
)

router = APIRouter()


def _q(model, db, hub_id):
    return HubQuery(model, db, hub_id)


# ============================================================================
# Dashboard
# ============================================================================

@router.get("/")
@htmx_view(module_id="sales", view_id="dashboard", partial_template="sales/partials/content.html", permissions="sales.view_sale")
async def dashboard(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    """Sales dashboard with KPIs."""
    today = datetime.now(UTC).date()
    week_ago = today - timedelta(days=7)

    base_q = _q(Sale, db, hub_id).filter(Sale.status == "completed")

    # Today stats
    sales_today_q = base_q.filter(func.date(Sale.created_at) == today)
    sales_count_today = await sales_today_q.count()
    sales_total_today = await sales_today_q.sum("total") or Decimal("0.00")

    # Week stats
    sales_week_q = base_q.filter(func.date(Sale.created_at) >= week_ago)
    sales_count_week = await sales_week_q.count()
    sales_total_week = await sales_week_q.sum("total") or Decimal("0.00")

    # Recent sales
    recent_sales = await (
        base_q.order_by(Sale.created_at.desc()).limit(5).all()
    )

    # Payment method stats for today
    payment_stats = {}
    pms = await _q(PaymentMethod, db, hub_id).filter(
        PaymentMethod.is_active == True  # noqa: E712
    ).all()
    for pm in pms:
        count = await sales_today_q.filter(
            Sale.payment_method_id == pm.id
        ).count()
        if count > 0:
            total = await sales_today_q.filter(
                Sale.payment_method_id == pm.id
            ).sum("total") or 0
            payment_stats[pm.name] = {"count": count, "total": total}

    return {
        "sales_count_today": sales_count_today,
        "sales_total_today": sales_total_today,
        "sales_count_week": sales_count_week,
        "sales_total_week": sales_total_week,
        "recent_sales": recent_sales,
        "payment_stats": payment_stats,
    }


# ============================================================================
# POS Screen
# ============================================================================

@router.get("/pos")
@htmx_view(module_id="sales", view_id="pos_screen", login_required=True, permissions="sales.add_sale")
async def pos_screen(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    """POS full-screen view."""
    settings_q = _q(SalesSettings, db, hub_id)
    settings = await settings_q.first()
    if settings is None:
        async with atomic(db) as session:
            settings = SalesSettings(hub_id=hub_id)
            session.add(settings)
            await session.flush()

    # Get inventory categories
    categories = []
    if settings.sync_products:
        try:
            from inventory.models import Category
            categories = await _q(Category, db, hub_id).filter(
                Category.is_active == True  # noqa: E712
            ).order_by(Category.sort_order, Category.name).all()
        except (ImportError, Exception):
            pass

    # Get service categories
    service_categories = []
    if settings.sync_services:
        try:
            from services.models import ServiceCategory
            service_categories = await _q(ServiceCategory, db, hub_id).filter(
                ServiceCategory.is_active == True  # noqa: E712
            ).order_by(ServiceCategory.sort_order, ServiceCategory.name).all()
        except (ImportError, Exception):
            pass

    payment_methods = await _q(PaymentMethod, db, hub_id).filter(
        PaymentMethod.is_active == True  # noqa: E712
    ).order_by(PaymentMethod.sort_order).all()

    return {
        "settings": settings,
        "categories": categories,
        "service_categories": service_categories,
        "payment_methods": payment_methods,
    }


@router.get("/pos/api/products")
async def get_products_for_pos(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
    category: str = "", search: str = "",
):
    """API: Products and services for POS grid with tax info."""
    settings = await _q(SalesSettings, db, hub_id).first()
    if settings is None:
        return JSONResponse({"success": True, "products": []})

    data = []

    # Load inventory products
    if settings.sync_products:
        try:
            from inventory.models import Product
            products_q = _q(Product, db, hub_id).filter(
                Product.is_active == True  # noqa: E712
            )
            if category and not category.startswith("svc-"):
                products_q = products_q.filter(Product.categories.any(id=uuid.UUID(category)))
            elif category and category.startswith("svc-"):
                products_q = products_q.filter(False)  # No inventory products in service category

            if search:
                products_q = products_q.filter(or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%"),
                ))

            products = await products_q.all()
            for p in products:
                tax_rate = float(p.get_tax_rate()) if hasattr(p, "get_tax_rate") else 0.0
                tax_class = p.get_effective_tax_class() if hasattr(p, "get_effective_tax_class") else None
                data.append({
                    "id": str(p.id),
                    "name": p.name,
                    "sku": getattr(p, "sku", ""),
                    "price": float(p.price),
                    "stock": getattr(p, "stock", 0),
                    "category": None,
                    "image": getattr(p, "image", None),
                    "product_type": getattr(p, "product_type", "physical"),
                    "is_service": getattr(p, "is_service", False),
                    "tax_rate": tax_rate,
                    "tax_class_name": tax_class.name if tax_class else "",
                })
        except (ImportError, Exception):
            pass

    # Load services
    if settings.sync_services:
        try:
            from services.models import Service
            services_q = _q(Service, db, hub_id).filter(
                Service.is_active == True  # noqa: E712
            )
            if category and category.startswith("svc-"):
                real_cat_id = category.replace("svc-", "")
                services_q = services_q.filter(Service.category_id == uuid.UUID(real_cat_id))
            elif category and not category.startswith("svc-"):
                services_q = services_q.filter(False)

            if search:
                services_q = services_q.filter(or_(
                    Service.name.ilike(f"%{search}%"),
                ))

            services = await services_q.all()
            for s in services:
                tax_rate = float(s.effective_tax_rate) if hasattr(s, "effective_tax_rate") else 0.0
                data.append({
                    "id": f"svc-{s.id}",
                    "name": s.name,
                    "sku": getattr(s, "slug", ""),
                    "price": float(s.price),
                    "stock": None,
                    "category": f"svc-{s.category_id}" if s.category_id else None,
                    "image": getattr(s, "image", None),
                    "product_type": "service",
                    "is_service": True,
                    "tax_rate": tax_rate,
                    "tax_class_name": "",
                })
        except (ImportError, Exception):
            pass

    return JSONResponse({"success": True, "products": data})


# ============================================================================
# Complete Sale
# ============================================================================

@router.post("/pos/api/complete-sale")
async def complete_sale(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """API: Complete a sale with multi-tax support."""
    try:
        body = await request.json()
        sale_data = CompleteSaleRequest(**body)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})

    try:
        # Validate require_customer
        settings = await _q(SalesSettings, db, hub_id).first()
        if settings and settings.require_customer:
            if not sale_data.customer_name and not sale_data.customer_id:
                return JSONResponse({"success": False, "error": "Customer is required"})

        async with atomic(db) as session:
            # Resolve payment method
            pm = None
            pm_name = ""
            if sale_data.payment_method_id:
                pm = await _q(PaymentMethod, session, hub_id).get(sale_data.payment_method_id)
                if pm:
                    pm_name = pm.name

            # Resolve customer
            customer_obj = None
            customer_name = sale_data.customer_name
            if sale_data.customer_id:
                try:
                    from customers.models import Customer
                    customer_obj = await _q(Customer, session, hub_id).get(sale_data.customer_id)
                    if customer_obj and not customer_name:
                        customer_name = customer_obj.name
                except (ImportError, Exception):
                    pass

            # Generate sale number
            sale_number = await generate_sale_number(session, hub_id)

            # Determine tax mode
            tax_included = True
            if settings:
                tax_included = settings.default_tax_included

            # Create sale
            sale = Sale(
                hub_id=hub_id,
                sale_number=sale_number,
                employee_id=user.id,
                payment_method_id=pm.id if pm else None,
                payment_method_name=pm_name,
                amount_tendered=sale_data.amount_tendered,
                customer_id=sale_data.customer_id,
                customer_name=customer_name,
                notes=sale_data.notes,
                status="completed",
            )
            session.add(sale)
            await session.flush()

            # Create sale items
            sale_items = []
            for item_data in sale_data.items:
                product_name = item_data.product_name
                product_sku = item_data.product_sku

                # Resolve product
                product_id = None
                if item_data.product_id:
                    try:
                        from inventory.models import Product
                        product = await _q(Product, session, hub_id).get(item_data.product_id)
                        if product:
                            product_id = product.id
                            product_name = product_name or product.name
                            product_sku = product_sku or getattr(product, "sku", "")
                            # Update stock for physical products
                            if not item_data.is_service:
                                product.stock -= int(item_data.quantity)
                    except (ImportError, Exception):
                        pass

                sale_item = SaleItem(
                    hub_id=hub_id,
                    sale_id=sale.id,
                    product_id=product_id,
                    product_name=product_name,
                    product_sku=product_sku,
                    is_service=item_data.is_service,
                    quantity=item_data.quantity,
                    unit_price=item_data.price,
                    discount_percent=item_data.discount,
                    tax_rate=item_data.tax_rate,
                    tax_class_name=item_data.tax_class_name,
                )
                sale_item.calculate_line_totals(tax_included=tax_included)
                session.add(sale_item)
                sale_items.append(sale_item)

            await session.flush()

            # Calculate totals
            sale.calculate_totals(items=sale_items)
            sale.calculate_change(sale_data.amount_tendered)

        # Emit sale.completed after commit — invoice/verifactu/other modules consume this
        try:
            from .events import emit_sale_completed
            await emit_sale_completed(
                request.app.state.event_bus,
                sale_id=str(sale.id),
                hub_id=str(hub_id),
                total=float(sale.total),
                subtotal=float(sale.subtotal),
                tax_amount=float(sale.tax_amount),
                items_count=len(sale_items),
                customer_id=str(sale.customer_id) if sale.customer_id else None,
                customer_name=sale.customer_name or "",
                sale_number=sale.sale_number or "",
            )
        except Exception:
            logger.exception("Failed to emit sale.completed for sale %s", sale.id)
            # NO re-raise: sale is already committed to DB; event failure must not break the flow

        return JSONResponse({
            "success": True,
            "sale_id": str(sale.id),
            "sale_number": sale.sale_number,
            "total": float(sale.total),
            "subtotal": float(sale.subtotal),
            "tax_amount": float(sale.tax_amount),
            "tax_breakdown": sale.tax_breakdown,
            "change": float(sale.change_due),
        })

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


# ============================================================================
# Sales History
# ============================================================================

@router.get("/history")
@htmx_view(module_id="sales", view_id="history", permissions="sales.view_sale")
async def sales_history(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
    search: str = "", status: str = "", date_from: str = "", date_to: str = "",
    user_id: str = "", order_by: str = "-created_at",
    page: int = 1, per_page: int = 25,
):
    """Sales history with filters and pagination."""
    query = _q(Sale, db, hub_id)

    if search:
        query = query.filter(or_(
            Sale.sale_number.ilike(f"%{search}%"),
            Sale.customer_name.ilike(f"%{search}%"),
        ))

    if date_from:
        query = query.filter(func.date(Sale.created_at) >= date_from)
    if date_to:
        query = query.filter(func.date(Sale.created_at) <= date_to)
    if status:
        query = query.filter(Sale.status == status)
    if user_id:
        query = query.filter(Sale.employee_id == uuid.UUID(user_id))

    # Sort
    sort_map = {
        "-created_at": Sale.created_at.desc(),
        "created_at": Sale.created_at,
        "-total": Sale.total.desc(),
        "total": Sale.total,
        "sale_number": Sale.sale_number,
        "-sale_number": Sale.sale_number.desc(),
    }
    query = query.order_by(sort_map.get(order_by, Sale.created_at.desc()))

    total = await query.count()
    sales = await query.offset((page - 1) * per_page).limit(per_page).all()

    # Check if HTMX targets the table container only
    hx_target = request.headers.get("HX-Target", "")
    if hx_target == "sales-table-container":
        # Return only the table body partial
        return {
            "_template": "sales/partials/sales_table_body.html",
            "sales": sales,
            "total": total,
            "page": page,
            "per_page": per_page,
            "has_next": (page * per_page) < total,
            "has_prev": page > 1,
            "search": search,
            "order_by": order_by,
            "date_from": date_from,
            "date_to": date_to,
            "status_filter": status,
        }

    return {
        "sales": sales,
        "total": total,
        "page": page,
        "per_page": per_page,
        "has_next": (page * per_page) < total,
        "has_prev": page > 1,
        "search": search,
        "order_by": order_by,
        "date_from": date_from,
        "date_to": date_to,
        "status_filter": status,
    }


@router.get("/history/api/list")
async def sales_list_ajax(
    request: Request, db: DbSession, hub_id: HubId,
    date_from: str = "", date_to: str = "", status: str = "",
):
    """API: Sales list for AJAX."""
    query = _q(Sale, db, hub_id)

    if date_from:
        query = query.filter(func.date(Sale.created_at) >= date_from)
    if date_to:
        query = query.filter(func.date(Sale.created_at) <= date_to)
    if status:
        query = query.filter(Sale.status == status)

    sales = await query.order_by(Sale.created_at.desc()).limit(100).all()

    data = [{
        "id": str(s.id),
        "sale_number": s.sale_number,
        "status": s.status,
        "total": float(s.total),
        "payment_method": s.payment_method_name,
        "customer_name": s.customer_name,
        "created_at": s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else "",
    } for s in sales]

    return JSONResponse({"success": True, "sales": data})


@router.get("/history/{sale_id}")
@htmx_view(module_id="sales", view_id="history", permissions="sales.view_sale")
async def sale_detail(
    request: Request, sale_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Sale detail view."""
    sale = await _q(Sale, db, hub_id).options(
        selectinload(Sale.items),
        selectinload(Sale.payment_method_rel),
    ).get(sale_id)
    if sale is None:
        return JSONResponse({"error": "Sale not found"}, status_code=404)

    items = [i for i in sale.items if not getattr(i, "is_deleted", False)]

    return {
        "_template": "sales/pages/detail.html",
        "_partial": "sales/partials/detail_content.html",
        "sale": sale,
        "items": items,
    }


@router.post("/history/{sale_id}/void")
async def void_sale(
    request: Request, sale_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Void a completed sale and restore stock."""
    sale = await _q(Sale, db, hub_id).options(
        selectinload(Sale.items),
    ).get(sale_id)
    if sale is None:
        return JSONResponse({"success": False, "error": "Sale not found"}, status_code=404)

    if sale.status == "voided":
        return JSONResponse({"success": False, "error": "Sale is already voided"})

    # Fiscal lock: cannot void a sale that has an active invoice linked.
    from modules.sales.services.sale_void_guard import (
        SaleCannotBeVoidedError,
        ensure_voidable,
    )
    try:
        await ensure_voidable(db, hub_id, sale)
    except SaleCannotBeVoidedError as exc:
        return JSONResponse(
            {"success": False, "error": str(exc)},
            status_code=409,
        )

    try:
        async with atomic(db) as session:
            # Restore stock for physical products
            for item in sale.items:
                if not item.is_service and item.product_id:
                    try:
                        from inventory.models import Product
                        product = await _q(Product, session, hub_id).get(item.product_id)
                        if product:
                            product.stock += int(item.quantity)
                    except (ImportError, Exception):
                        pass

            sale.status = "voided"

        # Emit sale.voided after commit — for future consumers
        try:
            from .events import emit_sale_voided
            await emit_sale_voided(
                request.app.state.event_bus,
                sale_id=str(sale.id),
                hub_id=str(hub_id),
                sale_number=sale.sale_number or "",
            )
        except Exception:
            logger.exception("Failed to emit sale.voided for sale %s", sale.id)

        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


# ============================================================================
# Reports
# ============================================================================

@router.get("/reports")
@htmx_view(module_id="sales", view_id="reports", permissions="sales.view_reports")
async def reports(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    """Reports page."""
    week_ago = datetime.now(UTC).date() - timedelta(days=7)
    sales_week_q = _q(Sale, db, hub_id).filter(
        Sale.status == "completed",
        func.date(Sale.created_at) >= week_ago,
    )

    return {
        "sales_count_week": await sales_week_q.count(),
        "sales_total_week": await sales_week_q.sum("total") or Decimal("0.00"),
    }


@router.get("/reports/api/stats")
async def reports_stats_ajax(
    request: Request, db: DbSession, hub_id: HubId,
    period: str = "week",
):
    """API: Report statistics by period with chart data."""
    today = datetime.now(UTC).date()

    period_map = {
        "day": today,
        "week": today - timedelta(days=7),
        "month": today - timedelta(days=30),
        "year": today - timedelta(days=365),
    }
    start_date = period_map.get(period, period_map["week"])

    sales_q = _q(Sale, db, hub_id).filter(
        Sale.status == "completed",
        func.date(Sale.created_at) >= start_date,
    )

    total_count = await sales_q.count()
    total_revenue = await sales_q.sum("total") or Decimal("0.00")

    stats = {
        "total_sales": total_count,
        "total_revenue": float(total_revenue),
        "avg_sale": float(total_revenue) / max(total_count, 1),
        "payment_methods": {},
        "chart_data": {"labels": [], "revenue": [], "count": []},
    }

    # Payment methods
    pms = await _q(PaymentMethod, db, hub_id).all()
    for pm in pms:
        count = await sales_q.filter(Sale.payment_method_id == pm.id).count()
        if count > 0:
            total = await sales_q.filter(Sale.payment_method_id == pm.id).sum("total") or 0
            stats["payment_methods"][pm.name] = {
                "label": pm.name,
                "count": count,
                "total": float(total),
                "percentage": round(count * 100 / max(total_count, 1)),
            }

    # Chart data: time-series
    # For simplicity, build labels and iterate. Full SQL truncation
    # would require raw queries — we build in Python for correctness.
    all_sales = await sales_q.order_by(Sale.created_at).all()

    if period == "day":
        hour_data: dict[int, dict] = {}
        for s in all_sales:
            h = s.created_at.hour
            if h not in hour_data:
                hour_data[h] = {"revenue": Decimal("0"), "count": 0}
            hour_data[h]["revenue"] += s.total
            hour_data[h]["count"] += 1
        for h in range(24):
            stats["chart_data"]["labels"].append(f"{h:02d}:00")
            d = hour_data.get(h)
            stats["chart_data"]["revenue"].append(float(d["revenue"]) if d else 0)
            stats["chart_data"]["count"].append(d["count"] if d else 0)

    elif period == "year":
        month_data: dict[str, dict] = {}
        for s in all_sales:
            key = s.created_at.strftime("%Y-%m")
            if key not in month_data:
                month_data[key] = {"revenue": Decimal("0"), "count": 0}
            month_data[key]["revenue"] += s.total
            month_data[key]["count"] += 1
        for i in range(12):
            month_date = (today.replace(day=1) - timedelta(days=30 * (11 - i))).replace(day=1)
            key = month_date.strftime("%Y-%m")
            stats["chart_data"]["labels"].append(calendar.month_abbr[month_date.month])
            d = month_data.get(key)
            stats["chart_data"]["revenue"].append(float(d["revenue"]) if d else 0)
            stats["chart_data"]["count"].append(d["count"] if d else 0)

    else:
        day_data: dict[str, dict] = {}
        for s in all_sales:
            key = s.created_at.strftime("%Y-%m-%d")
            if key not in day_data:
                day_data[key] = {"revenue": Decimal("0"), "count": 0}
            day_data[key]["revenue"] += s.total
            day_data[key]["count"] += 1
        num_days = 7 if period == "week" else 30
        for i in range(num_days):
            day = start_date + timedelta(days=i)
            if day > today:
                break
            key = day.strftime("%Y-%m-%d")
            stats["chart_data"]["labels"].append(day.strftime("%d/%m"))
            d = day_data.get(key)
            stats["chart_data"]["revenue"].append(float(d["revenue"]) if d else 0)
            stats["chart_data"]["count"].append(d["count"] if d else 0)

    return JSONResponse(stats)


# ============================================================================
# Settings
# ============================================================================

@router.get("/settings")
@htmx_view(module_id="sales", view_id="settings", permissions="sales.manage_settings")
async def settings_view(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    """Sales settings page."""
    settings_q = _q(SalesSettings, db, hub_id)
    settings = await settings_q.first()
    if settings is None:
        async with atomic(db) as session:
            settings = SalesSettings(hub_id=hub_id)
            session.add(settings)
            await session.flush()

    payment_methods = await _q(PaymentMethod, db, hub_id).order_by(
        PaymentMethod.sort_order
    ).all()

    return {
        "config": settings,
        "settings": settings,
        "payment_methods": payment_methods,
    }


@router.post("/settings/save")
async def settings_save(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    """Save sales settings."""
    try:
        body = await request.json()
        data = SalesSettingsUpdate(**body)

        settings = await _q(SalesSettings, db, hub_id).first()
        if settings is None:
            async with atomic(db) as session:
                settings = SalesSettings(hub_id=hub_id)
                session.add(settings)
                await session.flush()

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(settings, key, value)
        await db.flush()

        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@router.post("/settings/save-receipt-image")
async def settings_save_receipt_image(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Save receipt footer image (multipart upload)."""
    try:
        form = await request.form()
        settings = await _q(SalesSettings, db, hub_id).first()
        if settings is None:
            return JSONResponse({"success": False, "error": "Settings not found"}, status_code=404)

        image = form.get("receipt_footer_image")
        if image:
            # In FastAPI, save to media storage
            # For now, store the filename
            settings.receipt_footer_image = image.filename
            await db.flush()
            return JSONResponse({"success": True, "image_url": settings.receipt_footer_image})
        elif form.get("remove_image") == "true":
            settings.receipt_footer_image = ""
            await db.flush()
            return JSONResponse({"success": True, "image_url": None})
        else:
            return JSONResponse({"success": False, "error": "No image provided"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


# ============================================================================
# Payment Method CRUD
# ============================================================================

@router.post("/settings/payment-methods/create")
async def payment_method_create(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Create a payment method."""
    try:
        body = await request.json()
        data = PaymentMethodCreate(**body)

        async with atomic(db) as session:
            pm = PaymentMethod(hub_id=hub_id, **data.model_dump())
            session.add(pm)

        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@router.post("/settings/payment-methods/{pm_id}/update")
async def payment_method_update(
    request: Request, pm_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Update a payment method."""
    pm = await _q(PaymentMethod, db, hub_id).get(pm_id)
    if pm is None:
        return JSONResponse({"success": False, "error": "Payment method not found"}, status_code=404)

    try:
        body = await request.json()
        for key, value in body.items():
            if hasattr(pm, key):
                setattr(pm, key, value)
        await db.flush()
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@router.post("/settings/payment-methods/{pm_id}/delete")
async def payment_method_delete(
    request: Request, pm_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Soft-delete a payment method."""
    deleted = await _q(PaymentMethod, db, hub_id).delete(pm_id)
    if not deleted:
        return JSONResponse({"success": False, "error": "Payment method not found"}, status_code=404)
    return JSONResponse({"success": True})


# ============================================================================
# Active Cart (auto-save for POS)
# ============================================================================

@router.post("/pos/api/cart/save")
async def save_active_cart(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Save active cart data."""
    try:
        body = await request.json()
        items = body.get("items", [])

        existing = await _q(ActiveCart, db, hub_id).filter(
            ActiveCart.employee_id == user.id,
        ).first()

        if existing:
            existing.cart_data = {"items": items}
            await db.flush()
        else:
            async with atomic(db) as session:
                cart = ActiveCart(
                    hub_id=hub_id,
                    employee_id=user.id,
                    cart_data={"items": items},
                )
                session.add(cart)

        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.get("/pos/api/cart/load")
async def load_active_cart(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Load active cart data."""
    try:
        cart = await _q(ActiveCart, db, hub_id).filter(
            ActiveCart.employee_id == user.id,
        ).first()

        if cart:
            return JSONResponse({"success": True, "cart_data": cart.cart_data})
        return JSONResponse({"success": True, "cart_data": {"items": []}})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.post("/pos/api/cart/clear")
async def clear_active_cart(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Clear active cart."""
    try:
        cart = await _q(ActiveCart, db, hub_id).filter(
            ActiveCart.employee_id == user.id,
        ).first()
        if cart:
            await _q(ActiveCart, db, hub_id).hard_delete(cart.id)
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


# ============================================================================
# Parking Tickets
# ============================================================================

@router.post("/pos/api/park")
async def park_ticket(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Park a ticket (save cart temporarily)."""
    settings = await _q(SalesSettings, db, hub_id).first()
    if settings and not settings.enable_parked_tickets:
        return JSONResponse({"success": False, "error": "Parked tickets are disabled"})

    try:
        body = await request.json()
        items = body.get("items", [])
        notes = body.get("notes", "")

        if not items:
            return JSONResponse({"success": False, "error": "No items to park"})

        hours = settings.ticket_expiry_hours if settings else 24

        async with atomic(db) as session:
            ticket_number = await generate_ticket_number(session, hub_id)
            ticket = ParkedTicket(
                hub_id=hub_id,
                ticket_number=ticket_number,
                cart_data={"items": items},
                employee_id=user.id,
                notes=notes,
                expires_at=datetime.now(UTC) + timedelta(hours=hours),
            )
            session.add(ticket)
            await session.flush()

        return JSONResponse({
            "success": True,
            "ticket_number": ticket.ticket_number,
            "ticket_id": str(ticket.id),
            "expires_at": ticket.expires_at.strftime("%Y-%m-%d %H:%M"),
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.get("/pos/api/parked")
async def parked_tickets_list(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """List active parked tickets."""
    try:
        tickets = await _q(ParkedTicket, db, hub_id).order_by(
            ParkedTicket.created_at.desc()
        ).all()

        data = []
        for t in tickets:
            if not t.is_expired:
                data.append({
                    "id": str(t.id),
                    "ticket_number": t.ticket_number,
                    "employee_id": str(t.employee_id) if t.employee_id else "",
                    "notes": t.notes,
                    "created_at": t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
                    "expires_at": t.expires_at.strftime("%Y-%m-%d %H:%M"),
                    "age_hours": round(t.age_hours, 1),
                    "item_count": len(t.cart_data.get("items", [])),
                })

        return JSONResponse({"success": True, "tickets": data, "count": len(data)})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.post("/pos/api/recover/{ticket_id}")
async def recover_parked_ticket(
    request: Request, ticket_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Recover a parked ticket back to the cart."""
    ticket = await _q(ParkedTicket, db, hub_id).get(ticket_id)
    if ticket is None:
        return JSONResponse({"success": False, "error": "Ticket not found"}, status_code=404)

    if ticket.is_expired:
        return JSONResponse({
            "success": False,
            "error": f"Ticket {ticket.ticket_number} has expired",
        })

    cart_data = ticket.cart_data

    # Soft delete the recovered ticket
    await _q(ParkedTicket, db, hub_id).delete(ticket.id)

    return JSONResponse({"success": True, "cart_data": cart_data})
