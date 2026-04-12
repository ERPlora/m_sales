"""
Tests for sales kitchen hook: on_sale_completed emits kitchen.order_required.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from sales.hooks import _needs_kitchen, _on_sale_completed_action
from sales.models import Sale, SaleItem


class TestNeedsKitchen:
    def test_returns_false_for_plain_item(self, hub_id):
        item = SaleItem(
            hub_id=hub_id,
            product_name="Coffee",
            unit_price=Decimal("2.50"),
            quantity=Decimal("1.000"),
        )
        assert _needs_kitchen(item) is False

    def test_returns_true_when_item_has_needs_preparation(self, hub_id):
        item = SaleItem(
            hub_id=hub_id,
            product_name="Burger",
            unit_price=Decimal("12.00"),
            quantity=Decimal("1.000"),
        )
        # Simulate flag on item (could be set dynamically from product lookup)
        item.needs_preparation = True
        assert _needs_kitchen(item) is True

    def test_returns_true_when_product_has_flag(self, hub_id):
        item = SaleItem(
            hub_id=hub_id,
            product_name="Burger",
            unit_price=Decimal("12.00"),
            quantity=Decimal("1.000"),
        )
        product = MagicMock()
        product.needs_preparation = True
        product.categories = []
        item.product = product
        assert _needs_kitchen(item) is True

    def test_returns_true_when_category_is_kitchen(self, hub_id):
        item = SaleItem(
            hub_id=hub_id,
            product_name="Pizza",
            unit_price=Decimal("10.00"),
            quantity=Decimal("1.000"),
        )
        category = MagicMock()
        category.kitchen_category = True
        product = MagicMock()
        product.needs_preparation = False
        product.categories = [category]
        item.product = product
        assert _needs_kitchen(item) is True

    def test_returns_false_when_category_not_kitchen(self, hub_id):
        item = SaleItem(
            hub_id=hub_id,
            product_name="Drink",
            unit_price=Decimal("3.00"),
            quantity=Decimal("1.000"),
        )
        category = MagicMock()
        category.kitchen_category = False
        product = MagicMock()
        product.needs_preparation = False
        product.categories = [category]
        item.product = product
        assert _needs_kitchen(item) is False


class TestOnSaleCompletedAction:
    @pytest.fixture
    def hub_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def table_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def mock_bus(self):
        bus = MagicMock()
        bus.emit = AsyncMock()
        return bus

    def _make_sale(self, hub_id, status="completed", table_id=None, items=None):
        sale = Sale(
            hub_id=hub_id,
            sale_number="TEST-0001",
            status=status,
            channel="pos",
        )
        sale.table_id = table_id
        sale.items = items or []
        return sale

    def _make_kitchen_item(self, hub_id, product_id=None):
        item = SaleItem(
            hub_id=hub_id,
            product_name="Burger",
            unit_price=Decimal("12.00"),
            quantity=Decimal("2.000"),
            notes="No onions",
        )
        item.product_id = product_id or uuid.uuid4()
        item.needs_preparation = True
        return item

    def _make_retail_item(self, hub_id):
        item = SaleItem(
            hub_id=hub_id,
            product_name="Coke",
            unit_price=Decimal("2.00"),
            quantity=Decimal("1.000"),
            notes="",
        )
        item.product_id = uuid.uuid4()
        # no needs_preparation flag → defaults to False
        return item

    @pytest.mark.asyncio
    async def test_emits_kitchen_event_when_items_need_preparation(self, hub_id, table_id, mock_bus):
        product_id = uuid.uuid4()
        item = self._make_kitchen_item(hub_id, product_id=product_id)
        sale = self._make_sale(hub_id, table_id=table_id, items=[item])

        await _on_sale_completed_action(sale=sale, bus=mock_bus)

        mock_bus.emit.assert_awaited_once()
        call_kwargs = mock_bus.emit.call_args
        assert call_kwargs.args[0] == "kitchen.order_required"
        assert call_kwargs.kwargs["sale_id"] == str(sale.id)
        assert call_kwargs.kwargs["table_id"] == str(table_id)
        assert call_kwargs.kwargs["channel"] == "pos"
        items_payload = call_kwargs.kwargs["items"]
        assert len(items_payload) == 1
        assert items_payload[0]["product_id"] == str(product_id)
        assert items_payload[0]["quantity"] == 2.0
        assert items_payload[0]["notes"] == "No onions"

    @pytest.mark.asyncio
    async def test_no_emit_when_no_kitchen_items(self, hub_id, mock_bus):
        item = self._make_retail_item(hub_id)
        sale = self._make_sale(hub_id, items=[item])

        await _on_sale_completed_action(sale=sale, bus=mock_bus)

        mock_bus.emit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_emit_when_sale_not_completed(self, hub_id, mock_bus):
        item = self._make_kitchen_item(hub_id)
        sale = self._make_sale(hub_id, status="pending", items=[item])

        await _on_sale_completed_action(sale=sale, bus=mock_bus)

        mock_bus.emit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_emit_when_sale_is_none(self, mock_bus):
        await _on_sale_completed_action(sale=None, bus=mock_bus)
        mock_bus.emit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_table_id_is_none_when_not_dine_in(self, hub_id, mock_bus):
        item = self._make_kitchen_item(hub_id)
        sale = self._make_sale(hub_id, table_id=None, items=[item])

        await _on_sale_completed_action(sale=sale, bus=mock_bus)

        call_kwargs = mock_bus.emit.call_args
        assert call_kwargs.kwargs["table_id"] is None

    @pytest.mark.asyncio
    async def test_mixed_items_only_kitchen_in_payload(self, hub_id, mock_bus):
        kitchen_item = self._make_kitchen_item(hub_id)
        retail_item = self._make_retail_item(hub_id)
        sale = self._make_sale(hub_id, items=[kitchen_item, retail_item])

        await _on_sale_completed_action(sale=sale, bus=mock_bus)

        mock_bus.emit.assert_awaited_once()
        items_payload = mock_bus.emit.call_args.kwargs["items"]
        assert len(items_payload) == 1
        assert items_payload[0]["product_id"] == str(kitchen_item.product_id)
