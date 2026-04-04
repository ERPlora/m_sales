"""
Tests for sales module models.
"""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from decimal import Decimal

from sales.models import (
    SALE_STATUSES,
    STATUS_LABELS,
    ActiveCart,
    ParkedTicket,
    Sale,
    SaleItem,
)


class TestSalesSettings:
    def test_repr(self, sample_settings):
        assert "SalesSettings" in repr(sample_settings)

    def test_defaults(self, sample_settings):
        assert sample_settings.allow_cash is True
        assert sample_settings.allow_card is True
        assert sample_settings.allow_transfer is False
        assert sample_settings.sync_products is True
        assert sample_settings.sync_services is False
        assert sample_settings.require_customer is False
        assert sample_settings.allow_discounts is True
        assert sample_settings.enable_parked_tickets is True
        assert sample_settings.default_tax_included is True
        assert sample_settings.ticket_expiry_hours == 24


class TestPaymentMethod:
    def test_repr(self, sample_payment_method):
        assert "Cash" in repr(sample_payment_method)

    def test_defaults(self, sample_payment_method):
        assert sample_payment_method.is_active is True
        assert sample_payment_method.opens_cash_drawer is True
        assert sample_payment_method.requires_change is True


class TestSale:
    def test_repr(self, sample_sale):
        assert "20260404-0001" in repr(sample_sale)

    def test_status_label(self, sample_sale):
        assert sample_sale.status_label == "Completed"
        sample_sale.status = "voided"
        assert sample_sale.status_label == "Voided"

    def test_all_statuses_have_labels(self):
        for status in SALE_STATUSES:
            assert status in STATUS_LABELS

    def test_calculate_totals_single_item(self, hub_id):
        sale = Sale(hub_id=hub_id, sale_number="TEST-0001", status="completed")
        item = SaleItem(
            hub_id=hub_id,
            product_name="Widget",
            unit_price=Decimal("12.10"),
            quantity=Decimal("1.000"),
            tax_rate=Decimal("21.00"),
        )
        item.calculate_line_totals(tax_included=True)
        sale.calculate_totals(items=[item])

        assert sale.subtotal == item.net_amount
        assert sale.tax_amount == item.tax_amount
        assert sale.total == item.line_total
        assert "21.00" in sale.tax_breakdown

    def test_calculate_totals_multi_tax(self, hub_id):
        sale = Sale(hub_id=hub_id, sale_number="TEST-0002", status="completed")
        item1 = SaleItem(
            hub_id=hub_id,
            product_name="Food",
            unit_price=Decimal("11.00"),
            quantity=Decimal("1.000"),
            tax_rate=Decimal("10.00"),
        )
        item2 = SaleItem(
            hub_id=hub_id,
            product_name="Electronics",
            unit_price=Decimal("121.00"),
            quantity=Decimal("1.000"),
            tax_rate=Decimal("21.00"),
        )
        item1.calculate_line_totals(tax_included=True)
        item2.calculate_line_totals(tax_included=True)
        sale.calculate_totals(items=[item1, item2])

        assert "10.00" in sale.tax_breakdown
        assert "21.00" in sale.tax_breakdown
        assert sale.total == item1.line_total + item2.line_total

    def test_calculate_totals_with_discount(self, hub_id):
        sale = Sale(
            hub_id=hub_id, sale_number="TEST-0003", status="completed",
            discount_percent=Decimal("10.00"),
        )
        item = SaleItem(
            hub_id=hub_id,
            product_name="Widget",
            unit_price=Decimal("100.00"),
            quantity=Decimal("1.000"),
            tax_rate=Decimal("0.00"),
        )
        item.calculate_line_totals(tax_included=True)
        sale.calculate_totals(items=[item])

        assert sale.discount_amount == Decimal("10.00")
        assert sale.total == Decimal("90.00")

    def test_calculate_change(self, sample_sale):
        sample_sale.total = Decimal("85.00")
        change = sample_sale.calculate_change(100)
        assert change == Decimal("15.00")
        assert sample_sale.amount_tendered == Decimal("100")
        assert sample_sale.change_due == Decimal("15.00")

    def test_calculate_change_exact(self, sample_sale):
        sample_sale.total = Decimal("50.00")
        change = sample_sale.calculate_change(50)
        assert change == Decimal("0.00")

    def test_calculate_change_underpay(self, sample_sale):
        sample_sale.total = Decimal("50.00")
        change = sample_sale.calculate_change(30)
        assert change == Decimal("0.00")


class TestSaleItem:
    def test_repr(self, sample_sale_item):
        assert "Test Product" in repr(sample_sale_item)

    def test_calculate_line_totals_tax_included(self, hub_id):
        item = SaleItem(
            hub_id=hub_id,
            product_name="Widget",
            unit_price=Decimal("12.10"),
            quantity=Decimal("1.000"),
            tax_rate=Decimal("21.00"),
        )
        item.calculate_line_totals(tax_included=True)

        assert item.line_total == Decimal("12.10")
        assert item.net_amount == Decimal("10.00")
        assert item.tax_amount == Decimal("2.10")

    def test_calculate_line_totals_tax_excluded(self, hub_id):
        item = SaleItem(
            hub_id=hub_id,
            product_name="Widget",
            unit_price=Decimal("10.00"),
            quantity=Decimal("1.000"),
            tax_rate=Decimal("21.00"),
        )
        item.calculate_line_totals(tax_included=False)

        assert item.net_amount == Decimal("10.00")
        assert item.tax_amount == Decimal("2.10")
        assert item.line_total == Decimal("12.10")

    def test_calculate_line_totals_with_discount(self, hub_id):
        item = SaleItem(
            hub_id=hub_id,
            product_name="Widget",
            unit_price=Decimal("100.00"),
            quantity=Decimal("1.000"),
            tax_rate=Decimal("21.00"),
            discount_percent=Decimal("10.00"),
        )
        item.calculate_line_totals(tax_included=True)

        # 100 - 10% = 90.00 (with tax included)
        assert item.line_total == Decimal("90.00")

    def test_calculate_line_totals_quantity(self, hub_id):
        item = SaleItem(
            hub_id=hub_id,
            product_name="Widget",
            unit_price=Decimal("10.00"),
            quantity=Decimal("3.000"),
            tax_rate=Decimal("0.00"),
        )
        item.calculate_line_totals(tax_included=True)

        assert item.line_total == Decimal("30.00")
        assert item.net_amount == Decimal("30.00")
        assert item.tax_amount == Decimal("0.00")


class TestActiveCart:
    def test_repr(self, sample_active_cart):
        assert "1 items" in repr(sample_active_cart)

    def test_item_count(self, sample_active_cart):
        assert sample_active_cart.item_count == 1

    def test_item_count_empty(self, hub_id):
        cart = ActiveCart(hub_id=hub_id, employee_id=hub_id, cart_data={})
        assert cart.item_count == 0


class TestParkedTicket:
    def test_repr(self, sample_parked_ticket):
        assert "PARK-20260404-0001" in repr(sample_parked_ticket)

    def test_is_expired_false(self, sample_parked_ticket):
        assert sample_parked_ticket.is_expired is False

    def test_is_expired_true(self, hub_id):
        ticket = ParkedTicket(
            hub_id=hub_id,
            ticket_number="PARK-TEST-0001",
            cart_data={"items": []},
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        assert ticket.is_expired is True
