"""Initial sales module schema.

Revision ID: 001
Revises: -
Create Date: 2026-04-04

Creates tables: sales_settings, sales_payment_method, sales_sale,
sales_sale_item, sales_active_cart, sales_parked_ticket.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SalesSettings
    op.create_table(
        "sales_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hub_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("allow_cash", sa.Boolean(), server_default="true"),
        sa.Column("allow_card", sa.Boolean(), server_default="true"),
        sa.Column("allow_transfer", sa.Boolean(), server_default="false"),
        sa.Column("sync_products", sa.Boolean(), server_default="true"),
        sa.Column("sync_services", sa.Boolean(), server_default="false"),
        sa.Column("require_customer", sa.Boolean(), server_default="false"),
        sa.Column("allow_discounts", sa.Boolean(), server_default="true"),
        sa.Column("enable_parked_tickets", sa.Boolean(), server_default="true"),
        sa.Column("default_tax_included", sa.Boolean(), server_default="true"),
        sa.Column("ticket_expiry_hours", sa.Integer(), server_default="24"),
        sa.Column("receipt_header", sa.Text(), server_default=""),
        sa.Column("receipt_footer", sa.Text(), server_default=""),
        sa.Column("receipt_footer_image", sa.String(500), server_default=""),
        sa.UniqueConstraint("hub_id", name="uq_sales_settings_hub"),
    )

    # PaymentMethod
    op.create_table(
        "sales_payment_method",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hub_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("type", sa.String(20), server_default="cash"),
        sa.Column("icon", sa.String(50), server_default=""),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("opens_cash_drawer", sa.Boolean(), server_default="false"),
        sa.Column("requires_change", sa.Boolean(), server_default="false"),
    )

    # Sale
    op.create_table(
        "sales_sale",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hub_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sale_number", sa.String(50), nullable=False, index=True),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("subtotal", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("tax_amount", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("tax_breakdown", postgresql.JSONB(), server_default="{}"),
        sa.Column("discount_amount", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("discount_percent", sa.Numeric(5, 2), server_default="0.00"),
        sa.Column("total", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("payment_method_id", sa.Uuid(), sa.ForeignKey("sales_payment_method.id"), nullable=True),
        sa.Column("payment_method_name", sa.String(50), server_default=""),
        sa.Column("amount_tendered", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("change_due", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers_customer.id"), nullable=True),
        sa.Column("customer_name", sa.String(255), server_default=""),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), server_default=""),
    )
    op.create_index("ix_sales_hub_created", "sales_sale", ["hub_id", "created_at"])
    op.create_index("ix_sales_hub_number", "sales_sale", ["hub_id", "sale_number"])
    op.create_index("ix_sales_hub_status", "sales_sale", ["hub_id", "status"])
    op.create_index("ix_sales_hub_employee_created", "sales_sale", ["hub_id", "employee_id", "created_at"])

    # SaleItem
    op.create_table(
        "sales_sale_item",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hub_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sale_id", sa.Uuid(), sa.ForeignKey("sales_sale.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("product_sku", sa.String(100), server_default=""),
        sa.Column("is_service", sa.Boolean(), server_default="false"),
        sa.Column("quantity", sa.Numeric(10, 3), server_default="1.000"),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), server_default="0.00"),
        sa.Column("tax_rate", sa.Numeric(5, 2), server_default="0.00"),
        sa.Column("tax_class_name", sa.String(100), server_default=""),
        sa.Column("net_amount", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("tax_amount", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("line_total", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("modifiers", postgresql.JSONB(), server_default="{}"),
        sa.Column("notes", sa.Text(), server_default=""),
    )

    # ActiveCart
    op.create_table(
        "sales_active_cart",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hub_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("cart_data", postgresql.JSONB(), server_default="{}"),
        sa.UniqueConstraint("hub_id", "employee_id", name="uq_sales_active_cart_hub_employee"),
    )

    # ParkedTicket
    op.create_table(
        "sales_parked_ticket",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hub_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ticket_number", sa.String(30), nullable=False, index=True),
        sa.Column("cart_data", postgresql.JSONB(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_parked_hub_created", "sales_parked_ticket", ["hub_id", "created_at"])
    op.create_index("ix_parked_hub_expires", "sales_parked_ticket", ["hub_id", "expires_at"])


def downgrade() -> None:
    op.drop_table("sales_parked_ticket")
    op.drop_table("sales_active_cart")
    op.drop_table("sales_sale_item")
    op.drop_table("sales_sale")
    op.drop_table("sales_payment_method")
    op.drop_table("sales_settings")
