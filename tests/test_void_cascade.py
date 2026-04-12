"""Tests for void_sale() — F1.B cascade rectification flow.

Covers:
- void_sale(cascade_invoice=False) with active invoice → raises SaleCannotBeVoidedError
- void_sale(cascade_invoice=True)  with active invoice → cascade, sale voided, rect invoice created
- void_sale()                       without invoice   → works without cascade

Strategy: mock the AsyncSession and InvoiceService to avoid DB and fiscal complexity.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_sale(
    hub_id: uuid.UUID,
    sale_number: str = "S-001",
    notes: str = "",
) -> MagicMock:
    sale = MagicMock()
    sale.id = uuid.uuid4()
    sale.hub_id = hub_id
    sale.sale_number = sale_number
    sale.status = "completed"
    sale.notes = notes
    return sale


def _mock_session(row=None) -> AsyncMock:
    """Return AsyncSession mock whose execute().first() == row."""
    session = AsyncMock()
    result = MagicMock()
    result.first.return_value = row
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Test 1: cascade_invoice=False + active invoice → raises SaleCannotBeVoidedError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_void_sale_raises_when_invoice_active_and_no_cascade():
    """void_sale without cascade_invoice=True blocks with SaleCannotBeVoidedError."""
    hub_id = uuid.uuid4()
    inv_id = uuid.uuid4()
    sale = _fake_sale(hub_id, "S-001")

    inv_row = (inv_id, "TICKET", "2026-000001", "issued")
    session = _mock_session(inv_row)

    from sales.services.sale_service import void_sale
    from sales.services.sale_void_guard import SaleCannotBeVoidedError

    with pytest.raises(SaleCannotBeVoidedError) as exc_info:
        await void_sale(session, hub_id, sale, reason="test", cascade_invoice=False)

    assert "S-001" in str(exc_info.value)
    # Sale must NOT have been mutated
    assert sale.status == "completed"


# ---------------------------------------------------------------------------
# Test 2: cascade_invoice=True + active invoice → cascade, sale voided
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_void_sale_cascade_creates_rectification():
    """void_sale(cascade_invoice=True) calls InvoiceService.rectify and voids the sale."""
    hub_id = uuid.uuid4()
    inv_id = uuid.uuid4()
    rect_id = uuid.uuid4()
    sale = _fake_sale(hub_id, "S-002")

    inv_row = (inv_id, "TICKET", "2026-000002", "issued")
    session = _mock_session(inv_row)

    # Fake rectifying invoice returned by InvoiceService.rectify
    fake_rect_invoice = MagicMock()
    fake_rect_invoice.id = rect_id

    # void_sale does `from invoice.services.invoice_service import InvoiceService`
    # at runtime.  We stub the whole module so no SQLAlchemy models are loaded.
    mock_svc_instance = MagicMock()
    mock_svc_instance.rectify = AsyncMock(return_value=fake_rect_invoice)

    mock_invoice_service_module = MagicMock()
    mock_invoice_service_module.InvoiceService = MagicMock(return_value=mock_svc_instance)

    import sys
    # Pre-populate sys.modules so the lazy import inside void_sale hits our stub
    sys.modules.setdefault("invoice", MagicMock())
    sys.modules["invoice.services"] = MagicMock()
    sys.modules["invoice.services.invoice_service"] = mock_invoice_service_module

    from sales.services.sale_service import void_sale

    result = await void_sale(
        session,
        hub_id,
        sale,
        reason="return from customer",
        cascade_invoice=True,
        bus=None,  # bus=None skips event emission in test
    )

    # Restore so other tests are not affected
    del sys.modules["invoice.services"]
    del sys.modules["invoice.services.invoice_service"]

    # Return dict
    assert result["sale_number"] == "S-002"
    assert result["status"] == "voided"
    assert result["cascaded"] is True
    assert result["rectification_id"] == str(rect_id)

    # Sale voided with traceability note
    assert sale.status == "voided"
    assert "VOIDED" in sale.notes
    assert "return from customer" in sale.notes

    # InvoiceService.rectify was called with original invoice id + reason
    mock_svc_instance.rectify.assert_awaited_once_with(
        inv_id, reason="return from customer"
    )


# ---------------------------------------------------------------------------
# Test 3: no invoice → void without cascade, no error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_void_sale_no_invoice_succeeds_without_cascade():
    """void_sale with no linked invoice voids the sale unconditionally."""
    hub_id = uuid.uuid4()
    sale = _fake_sale(hub_id, "S-003", notes="original note")
    session = _mock_session(None)  # No invoice row

    from sales.services.sale_service import void_sale

    result = await void_sale(
        session, hub_id, sale, reason="test void", cascade_invoice=False, bus=None,
    )

    assert result["status"] == "voided"
    assert result["cascaded"] is False
    assert result["rectification_id"] is None
    assert sale.status == "voided"
    assert "VOIDED" in sale.notes
    assert "test void" in sale.notes
    # Original notes preserved
    assert "original note" in sale.notes
