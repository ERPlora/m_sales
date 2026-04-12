"""Add cash_session_id to sales_sale.

Revision ID: 003
Revises: 002
Create Date: 2026-04-12

Loose FK to cash_register's CashSession — cash_register may not be installed,
so no ForeignKeyConstraint. Indexed for efficient per-session queries.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_sale",
        sa.Column("cash_session_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_sales_sale_cash_session_id",
        "sales_sale",
        ["cash_session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sales_sale_cash_session_id", table_name="sales_sale")
    op.drop_column("sales_sale", "cash_session_id")
