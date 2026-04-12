"""Add table_id to sales_sale.

Revision ID: 004
Revises: 003
Create Date: 2026-04-12

Loose FK to tables_table — tables module may not be installed, so no
ForeignKeyConstraint. Nullable UUID with index for dine-in table tracking.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_sale",
        sa.Column("table_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_sales_sale_table_id",
        "sales_sale",
        ["table_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sales_sale_table_id", table_name="sales_sale")
    op.drop_column("sales_sale", "table_id")
