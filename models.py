"""
Sales module models — SQLAlchemy 2.0.

Models: SalesSettings, PaymentMethod, Sale, SaleItem, ActiveCart, ParkedTicket.

Sales is the universal sales engine. It has no POS interface (that's the pos module).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, UTC
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from runtime.models.base import HubBaseModel

if TYPE_CHECKING:
    pass


# ============================================================================
# Sales Settings (singleton per hub)
# ============================================================================

class SalesSettings(HubBaseModel):
    """Per-hub sales configuration."""

    __tablename__ = "sales_settings"
    __table_args__ = (
        UniqueConstraint("hub_id", name="uq_sales_settings_hub"),
    )

    # Payment methods
    allow_cash: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    allow_card: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    allow_transfer: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )

    # POS sync
    sync_products: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    sync_services: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )

    # Other options
    require_customer: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )
    allow_discounts: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    enable_parked_tickets: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    default_tax_included: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    ticket_expiry_hours: Mapped[int] = mapped_column(
        Integer, default=24, server_default="24",
    )

    # Receipt configuration
    receipt_header: Mapped[str] = mapped_column(
        Text, default="", server_default="",
    )
    receipt_footer: Mapped[str] = mapped_column(
        Text, default="", server_default="",
    )
    receipt_footer_image: Mapped[str] = mapped_column(
        String(500), default="", server_default="",
    )

    def __repr__(self) -> str:
        return f"<SalesSettings hub={self.hub_id}>"


# ============================================================================
# Payment Method
# ============================================================================

PAYMENT_TYPES = ("cash", "card", "transfer", "other")


class PaymentMethod(HubBaseModel):
    """Payment method configuration."""

    __tablename__ = "sales_payment_method"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(
        String(20), default="cash", server_default="cash",
    )
    icon: Mapped[str] = mapped_column(
        String(50), default="", server_default="",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0",
    )
    opens_cash_drawer: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )
    requires_change: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )

    # Relationships
    sales: Mapped[list[Sale]] = relationship(
        "Sale", back_populates="payment_method_rel", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<PaymentMethod {self.name!r}>"


# ============================================================================
# Sale
# ============================================================================

SALE_STATUSES = ("draft", "pending", "completed", "voided", "refunded")

STATUS_LABELS = {
    "draft": "Draft",
    "pending": "Pending Payment",
    "completed": "Completed",
    "voided": "Voided",
    "refunded": "Refunded",
}


class Sale(HubBaseModel):
    """Sale transaction with multi-tax breakdown support."""

    __tablename__ = "sales_sale"
    __table_args__ = (
        Index("ix_sales_hub_created", "hub_id", "created_at"),
        Index("ix_sales_hub_number", "hub_id", "sale_number"),
        Index("ix_sales_hub_status", "hub_id", "status"),
        Index("ix_sales_hub_employee_created", "hub_id", "employee_id", "created_at"),
        Index("ix_sales_hub_source_module", "hub_id", "source_module"),
    )

    sale_number: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft",
    )

    # Amounts
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00",
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00",
    )
    tax_breakdown: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}",
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00",
    )
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00"), server_default="0.00",
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00",
    )

    # Payment
    payment_method_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sales_payment_method.id"), nullable=True,
    )
    payment_method_name: Mapped[str] = mapped_column(
        String(50), default="", server_default="",
    )
    amount_tendered: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00",
    )
    change_due: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00",
    )

    # Customer (optional FK to customers module)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("customers_customer.id"), nullable=True,
    )
    customer_name: Mapped[str] = mapped_column(
        String(255), default="", server_default="",
    )

    # Employee
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True,
    )

    notes: Mapped[str] = mapped_column(
        Text, default="", server_default="",
    )

    # Multi-channel fields (Phase 1 of sales restructuring)
    source_module: Mapped[str] = mapped_column(
        String(50), default="", server_default="",
        index=True,
    )
    channel: Mapped[str] = mapped_column(
        String(50), default="", server_default="",
    )
    priority: Mapped[str] = mapped_column(
        String(20), default="normal", server_default="normal",
    )
    customer_phone: Mapped[str] = mapped_column(
        String(50), default="", server_default="",
    )
    delivery_address: Mapped[str] = mapped_column(
        Text, default="", server_default="",
    )
    requested_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    internal_notes: Mapped[str] = mapped_column(
        Text, default="", server_default="",
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True,
    )

    # Cash register session (loose FK — cash_register may not be installed)
    cash_session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True, index=True,
    )

    # Table reference (dine-in). No FK real cross-module — only UUID indexed.
    table_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True, index=True,
        comment="Table where this sale was taken (dine-in). Optional.",
    )

    # Relationships
    payment_method_rel: Mapped[PaymentMethod | None] = relationship(
        "PaymentMethod", back_populates="sales", lazy="joined",
    )
    items: Mapped[list[SaleItem]] = relationship(
        "SaleItem", back_populates="sale", cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Sale #{self.sale_number}>"

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    def calculate_totals(self, items: list[SaleItem] | None = None) -> None:
        """
        Calculate sale totals with multi-tax breakdown.
        Aggregates tax by rate from items.
        Pass items explicitly in async context (no lazy load).
        """
        sale_items = items if items is not None else self.items
        total_net = Decimal("0.00")
        total_tax = Decimal("0.00")
        total_gross = Decimal("0.00")
        breakdown: dict[str, dict[str, Decimal]] = defaultdict(
            lambda: {"base": Decimal("0.00"), "tax": Decimal("0.00")}
        )

        for item in sale_items:
            total_net += item.net_amount
            total_tax += item.tax_amount
            total_gross += item.line_total

            rate_key = str(item.tax_rate)
            breakdown[rate_key]["base"] += item.net_amount
            breakdown[rate_key]["tax"] += item.tax_amount

        self.subtotal = total_net
        self.tax_amount = total_tax
        self.tax_breakdown = {
            k: {"base": float(v["base"]), "tax": float(v["tax"])}
            for k, v in breakdown.items()
        }

        # Apply discount
        discount_pct = self.discount_percent if self.discount_percent is not None else Decimal("0.00")
        if discount_pct > 0:
            self.discount_amount = (
                total_gross * discount_pct / Decimal("100")
            ).quantize(Decimal("0.01"))

        discount_amt = self.discount_amount if self.discount_amount is not None else Decimal("0.00")
        self.total = total_gross - discount_amt

    def calculate_change(self, amount_tendered: Decimal | float | str) -> Decimal:
        """Calculate change due from amount tendered."""
        self.amount_tendered = Decimal(str(amount_tendered))
        self.change_due = max(self.amount_tendered - self.total, Decimal("0.00"))
        return self.change_due


# ============================================================================
# Sale Item
# ============================================================================

class SaleItem(HubBaseModel):
    """Line item within a sale, with per-item tax calculation."""

    __tablename__ = "sales_sale_item"

    sale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sales_sale.id", ondelete="CASCADE"), nullable=False,
    )

    # Product reference (FK to inventory)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True,
    )
    product_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    product_sku: Mapped[str] = mapped_column(
        String(100), default="", server_default="",
    )
    is_service: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )

    # Amounts
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), default=Decimal("1.000"), server_default="1.000",
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False,
    )
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00"), server_default="0.00",
    )

    # Per-item tax
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00"), server_default="0.00",
    )
    tax_class_name: Mapped[str] = mapped_column(
        String(100), default="", server_default="",
    )
    net_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00",
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00",
    )
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00",
    )

    # Modifiers / notes
    modifiers: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}",
    )
    notes: Mapped[str] = mapped_column(
        Text, default="", server_default="",
    )

    # Relationships
    sale: Mapped[Sale] = relationship("Sale", back_populates="items")

    def __repr__(self) -> str:
        return f"<SaleItem {self.quantity}x {self.product_name!r}>"

    def calculate_line_totals(self, tax_included: bool = True) -> None:
        """
        Calculate line totals including per-item tax.
        Supports both tax-included and tax-excluded pricing.
        """
        # Ensure numeric defaults (SQLAlchemy column defaults only apply on DB flush)
        discount_pct = self.discount_percent if self.discount_percent is not None else Decimal("0.00")
        tax_rate = self.tax_rate if self.tax_rate is not None else Decimal("0.00")

        # Calculate discount
        discount_amount = self.unit_price * (discount_pct / Decimal("100"))
        discounted_price = self.unit_price - discount_amount

        if tax_included:
            tax_divisor = Decimal("1") + (tax_rate / Decimal("100"))
            net_unit = discounted_price / tax_divisor
            self.net_amount = (net_unit * self.quantity).quantize(Decimal("0.01"))
            self.line_total = (discounted_price * self.quantity).quantize(Decimal("0.01"))
            self.tax_amount = (self.line_total - self.net_amount).quantize(Decimal("0.01"))
        else:
            self.net_amount = (discounted_price * self.quantity).quantize(Decimal("0.01"))
            self.tax_amount = (
                self.net_amount * (tax_rate / Decimal("100"))
            ).quantize(Decimal("0.01"))
            self.line_total = (self.net_amount + self.tax_amount).quantize(Decimal("0.01"))


# ============================================================================
# Active Cart (persists across restarts)
# ============================================================================

class ActiveCart(HubBaseModel):
    """
    Active POS cart persisted in the database.
    One cart per employee per hub.
    """

    __tablename__ = "sales_active_cart"
    __table_args__ = (
        UniqueConstraint("hub_id", "employee_id", name="uq_sales_active_cart_hub_employee"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False,
    )
    cart_data: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}",
    )

    def __repr__(self) -> str:
        count = len(self.cart_data.get("items", []))
        return f"<ActiveCart ({count} items)>"

    @property
    def item_count(self) -> int:
        return len(self.cart_data.get("items", []))

    @property
    def age_minutes(self) -> float:
        if self.updated_at is None:
            return 0.0
        delta = datetime.now(UTC) - self.updated_at
        return delta.total_seconds() / 60


# ============================================================================
# Parked Ticket
# ============================================================================

class ParkedTicket(HubBaseModel):
    """Temporarily parked sale ticket."""

    __tablename__ = "sales_parked_ticket"
    __table_args__ = (
        Index("ix_parked_hub_created", "hub_id", "created_at"),
        Index("ix_parked_hub_expires", "hub_id", "expires_at"),
    )

    ticket_number: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True,
    )
    cart_data: Mapped[dict] = mapped_column(
        JSONB, nullable=False,
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True,
    )
    notes: Mapped[str] = mapped_column(
        Text, default="", server_default="",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ParkedTicket #{self.ticket_number}>"

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.expires_at

    @property
    def age_hours(self) -> float:
        if self.created_at is None:
            return 0.0
        delta = datetime.now(UTC) - self.created_at
        return delta.total_seconds() / 3600


# ============================================================================
# Helper: generate_sale_number (async)
# ============================================================================

async def generate_sale_number(session: Any, hub_id: uuid.UUID) -> str:
    """Generate a unique sale number for the hub: YYYYMMDD-0001."""
    from runtime.models.queryset import HubQuery

    today = datetime.now(UTC)
    prefix = today.strftime("%Y%m%d")

    last_sale = await (
        HubQuery(Sale, session, hub_id)
        .filter(Sale.sale_number.startswith(prefix))
        .order_by(Sale.sale_number.desc())
        .first()
    )

    if last_sale:
        try:
            last_num = int(last_sale.sale_number.split("-")[-1])
            new_num = last_num + 1
        except (ValueError, IndexError):
            new_num = 1
    else:
        new_num = 1

    return f"{prefix}-{new_num:04d}"


async def generate_ticket_number(session: Any, hub_id: uuid.UUID) -> str:
    """Generate a unique parked ticket number for the hub: PARK-YYYYMMDD-0001."""
    from runtime.models.queryset import HubQuery

    today = datetime.now(UTC).strftime("%Y%m%d")
    prefix = f"PARK-{today}"

    last_ticket = await (
        HubQuery(ParkedTicket, session, hub_id)
        .filter(ParkedTicket.ticket_number.startswith(prefix))
        .order_by(ParkedTicket.ticket_number.desc())
        .first()
    )

    if last_ticket:
        try:
            last_num = int(last_ticket.ticket_number.split("-")[-1])
            new_num = last_num + 1
        except (ValueError, IndexError):
            new_num = 1
    else:
        new_num = 1

    return f"PARK-{today}-{new_num:04d}"
