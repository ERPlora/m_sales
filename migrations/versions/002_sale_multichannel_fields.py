"""Add multichannel fields to sales_sale.

Revision ID: 002
Revises: 001
Create Date: 2026-04-12

Phase 1 of sales restructuring: source_module, channel, priority,
customer_phone, delivery_address, requested_date, internal_notes, assigned_to.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_sale",
        sa.Column(
            "source_module",
            sa.String(50),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "sales_sale",
        sa.Column(
            "channel",
            sa.String(50),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "sales_sale",
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            server_default="normal",
        ),
    )
    op.add_column(
        "sales_sale",
        sa.Column(
            "customer_phone",
            sa.String(50),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "sales_sale",
        sa.Column(
            "delivery_address",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "sales_sale",
        sa.Column(
            "requested_date",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "sales_sale",
        sa.Column(
            "internal_notes",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "sales_sale",
        sa.Column(
            "assigned_to",
            sa.Uuid(),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_sales_hub_source_module",
        "sales_sale",
        ["hub_id", "source_module"],
    )


def downgrade() -> None:
    op.drop_index("ix_sales_hub_source_module", table_name="sales_sale")
    op.drop_column("sales_sale", "assigned_to")
    op.drop_column("sales_sale", "internal_notes")
    op.drop_column("sales_sale", "requested_date")
    op.drop_column("sales_sale", "delivery_address")
    op.drop_column("sales_sale", "customer_phone")
    op.drop_column("sales_sale", "priority")
    op.drop_column("sales_sale", "channel")
    op.drop_column("sales_sale", "source_module")
