"""
Test fixtures for the sales module.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, UTC
from decimal import Decimal

import pytest

from sales.models import (
    ActiveCart,
    ParkedTicket,
    PaymentMethod,
    Sale,
    SaleItem,
    SalesSettings,
)


@pytest.fixture
def hub_id():
    """Test hub UUID."""
    return uuid.uuid4()


@pytest.fixture
def sample_settings(hub_id):
    """Create sample sales settings (not persisted)."""
    return SalesSettings(
        hub_id=hub_id,
        allow_cash=True,
        allow_card=True,
        allow_transfer=False,
        sync_products=True,
        sync_services=False,
        require_customer=False,
        allow_discounts=True,
        enable_parked_tickets=True,
        default_tax_included=True,
        ticket_expiry_hours=24,
    )


@pytest.fixture
def sample_payment_method(hub_id):
    """Create a sample payment method (not persisted)."""
    return PaymentMethod(
        hub_id=hub_id,
        name="Cash",
        type="cash",
        icon="cash-outline",
        is_active=True,
        sort_order=0,
        opens_cash_drawer=True,
        requires_change=True,
    )


@pytest.fixture
def sample_sale(hub_id):
    """Create a sample sale (not persisted)."""
    return Sale(
        hub_id=hub_id,
        sale_number="20260404-0001",
        status="completed",
        subtotal=Decimal("82.64"),
        tax_amount=Decimal("17.36"),
        total=Decimal("100.00"),
        payment_method_name="Cash",
        amount_tendered=Decimal("100.00"),
        change_due=Decimal("0.00"),
        customer_name="Test Customer",
    )


@pytest.fixture
def sample_sale_item(hub_id, sample_sale):
    """Create a sample sale item (not persisted)."""
    return SaleItem(
        hub_id=hub_id,
        sale_id=sample_sale.id if sample_sale.id else uuid.uuid4(),
        product_name="Test Product",
        product_sku="TST-001",
        quantity=Decimal("2.000"),
        unit_price=Decimal("50.00"),
        tax_rate=Decimal("21.00"),
        net_amount=Decimal("82.64"),
        tax_amount=Decimal("17.36"),
        line_total=Decimal("100.00"),
    )


@pytest.fixture
def sample_active_cart(hub_id):
    """Create a sample active cart (not persisted)."""
    return ActiveCart(
        hub_id=hub_id,
        employee_id=uuid.uuid4(),
        cart_data={"items": [{"name": "Widget", "price": 9.99, "qty": 1}]},
    )


@pytest.fixture
def sample_parked_ticket(hub_id):
    """Create a sample parked ticket (not persisted)."""
    return ParkedTicket(
        hub_id=hub_id,
        ticket_number="PARK-20260404-0001",
        cart_data={"items": [{"name": "Widget", "price": 9.99, "qty": 1}]},
        employee_id=uuid.uuid4(),
        notes="Quick park",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
