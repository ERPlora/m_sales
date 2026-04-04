"""
Pydantic schemas for sales module.

Replaces Django forms — used for request validation and form rendering.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ============================================================================
# Sales Settings
# ============================================================================

class SalesSettingsUpdate(BaseModel):
    allow_cash: bool | None = None
    allow_card: bool | None = None
    allow_transfer: bool | None = None
    sync_products: bool | None = None
    sync_services: bool | None = None
    require_customer: bool | None = None
    allow_discounts: bool | None = None
    enable_parked_tickets: bool | None = None
    default_tax_included: bool | None = None
    ticket_expiry_hours: int | None = Field(default=None, ge=1, le=168)
    receipt_header: str | None = None
    receipt_footer: str | None = None


# ============================================================================
# Payment Method
# ============================================================================

class PaymentMethodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: str = Field(default="cash", max_length=20)
    icon: str = Field(default="", max_length=50)
    is_active: bool = True
    sort_order: int = 0
    opens_cash_drawer: bool = False
    requires_change: bool = False


class PaymentMethodUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    type: str | None = Field(default=None, max_length=20)
    icon: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    opens_cash_drawer: bool | None = None
    requires_change: bool | None = None


# ============================================================================
# Sale (complete sale from POS)
# ============================================================================

class SaleItemInput(BaseModel):
    """Single item in a sale request from POS."""
    product_id: uuid.UUID | None = None
    product_name: str = ""
    product_sku: str = ""
    is_service: bool = False
    quantity: Decimal = Field(default=Decimal("1"), ge=Decimal("0.001"))
    price: Decimal
    discount: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0)
    tax_class_name: str = ""


class CompleteSaleRequest(BaseModel):
    """Request to complete a sale from POS."""
    items: list[SaleItemInput] = Field(min_length=1)
    payment_method_id: uuid.UUID | None = None
    amount_tendered: Decimal = Field(default=Decimal("0"))
    customer_id: uuid.UUID | None = None
    customer_name: str = ""
    notes: str = ""


class CompleteSaleResponse(BaseModel):
    success: bool
    sale_id: str | None = None
    sale_number: str | None = None
    total: float | None = None
    subtotal: float | None = None
    tax_amount: float | None = None
    tax_breakdown: dict | None = None
    change: float | None = None
    error: str | None = None


# ============================================================================
# Sale Response (for API)
# ============================================================================

class SaleResponse(BaseModel):
    id: uuid.UUID
    sale_number: str
    status: str
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total: Decimal
    payment_method_name: str
    customer_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SaleListResponse(BaseModel):
    sales: list[SaleResponse]
    total: int


# ============================================================================
# Active Cart
# ============================================================================

class CartSaveRequest(BaseModel):
    items: list[dict] = []


# ============================================================================
# Parked Ticket
# ============================================================================

class ParkTicketRequest(BaseModel):
    items: list[dict] = Field(min_length=1)
    notes: str = ""


# ============================================================================
# Filters
# ============================================================================

class SaleFilter(BaseModel):
    search: str = ""
    status: str = ""
    date_from: str = ""
    date_to: str = ""
    user_id: uuid.UUID | None = None
    order_by: str = "-created_at"
    page: int = 1
    per_page: int = 25


class ReportStatsFilter(BaseModel):
    period: str = "week"  # day, week, month, year
