"""
Tests for Sale.table_id field (dine-in table tracking).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sales.models import Sale


class TestSaleTableId:
    def test_table_id_defaults_to_none(self, hub_id):
        sale = Sale(hub_id=hub_id, sale_number="TEST-0001", status="draft")
        assert sale.table_id is None

    def test_table_id_can_be_set(self, hub_id):
        table_id = uuid.uuid4()
        sale = Sale(
            hub_id=hub_id,
            sale_number="TEST-0001",
            status="completed",
            table_id=table_id,
        )
        assert sale.table_id == table_id

    def test_table_id_round_trip(self, hub_id):
        """table_id preserves the UUID value after assignment."""
        original_id = uuid.uuid4()
        sale = Sale(hub_id=hub_id, sale_number="TEST-0001", status="completed")
        sale.table_id = original_id
        assert sale.table_id == original_id

    def test_table_id_can_be_cleared(self, hub_id):
        table_id = uuid.uuid4()
        sale = Sale(
            hub_id=hub_id,
            sale_number="TEST-0001",
            status="draft",
            table_id=table_id,
        )
        assert sale.table_id == table_id
        sale.table_id = None
        assert sale.table_id is None

    def test_sale_without_table_id_is_valid(self, hub_id):
        """Non-dine-in sales (retail, delivery) have no table_id."""
        sale = Sale(
            hub_id=hub_id,
            sale_number="TEST-0002",
            status="completed",
            channel="pos",
            subtotal=Decimal("10.00"),
            total=Decimal("10.00"),
        )
        assert sale.table_id is None
