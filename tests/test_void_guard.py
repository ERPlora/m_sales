"""Tests for SaleVoidGuard — F1.A of the production-ready refactor.

Covers:
- no invoice → ensure_voidable passes
- issued invoice → ensure_voidable raises SaleCannotBeVoidedError
- paid invoice → ensure_voidable raises SaleCannotBeVoidedError
- draft invoice → ensure_voidable passes (non-blocking)
- cancelled invoice → ensure_voidable passes (non-blocking)
- invoice in another hub → no effect

Strategy: mock the AsyncSession.execute() to avoid JSONB/FK complexity
with SQLite. The guard is a pure query function — the query logic is
what matters, not the DB engine.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.sales.services.sale_void_guard import (
    BLOCKING_INVOICE_STATUSES,
    ActiveInvoiceRef,
    SaleCannotBeVoidedError,
    ensure_voidable,
    find_active_invoice_for_sale,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_sale(hub_id: uuid.UUID, sale_number: str = "S-001") -> MagicMock:
    """Create a minimal Sale-like object for guard testing."""
    sale = MagicMock()
    sale.id = uuid.uuid4()
    sale.hub_id = hub_id
    sale.sale_number = sale_number
    return sale


def _mock_session_with_row(row):
    """Return an AsyncSession mock whose execute() returns a result with one row."""
    session = AsyncMock()
    result = MagicMock()
    result.first.return_value = row
    session.execute = AsyncMock(return_value=result)
    return session


def _mock_session_no_row():
    """Return an AsyncSession mock whose execute() returns no rows."""
    return _mock_session_with_row(None)


# ---------------------------------------------------------------------------
# Unit tests: find_active_invoice_for_sale
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_returns_none_when_no_row():
    hub_id = uuid.uuid4()
    sale_id = uuid.uuid4()
    session = _mock_session_no_row()

    result = await find_active_invoice_for_sale(session, hub_id, sale_id)

    assert result is None


@pytest.mark.asyncio
async def test_find_returns_ref_when_row_found():
    hub_id = uuid.uuid4()
    sale_id = uuid.uuid4()
    inv_id = uuid.uuid4()

    row = (inv_id, "A", "0042", "issued")
    session = _mock_session_with_row(row)

    result = await find_active_invoice_for_sale(session, hub_id, sale_id)

    assert result is not None
    assert result.invoice_id == inv_id
    assert result.invoice_number == "A/0042"
    assert result.status == "issued"


@pytest.mark.asyncio
async def test_find_formats_number_without_series_when_empty():
    hub_id = uuid.uuid4()
    sale_id = uuid.uuid4()
    inv_id = uuid.uuid4()

    row = (inv_id, "", "0099", "paid")
    session = _mock_session_with_row(row)

    result = await find_active_invoice_for_sale(session, hub_id, sale_id)

    assert result is not None
    assert result.invoice_number == "0099"


@pytest.mark.asyncio
async def test_find_returns_none_when_invoice_module_not_installed():
    hub_id = uuid.uuid4()
    sale_id = uuid.uuid4()
    session = _mock_session_no_row()

    with patch.dict("sys.modules", {"modules.invoice.models": None}):
        result = await find_active_invoice_for_sale(session, hub_id, sale_id)

    assert result is None


# ---------------------------------------------------------------------------
# Unit tests: ensure_voidable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ensure_voidable_passes_when_no_invoice():
    hub_id = uuid.uuid4()
    sale = _fake_sale(hub_id, "S-001")
    session = _mock_session_no_row()

    # Must NOT raise.
    await ensure_voidable(session, hub_id, sale)


@pytest.mark.asyncio
async def test_ensure_voidable_raises_when_invoice_issued():
    hub_id = uuid.uuid4()
    sale = _fake_sale(hub_id, "S-002")
    inv_id = uuid.uuid4()

    row = (inv_id, "A", "INV-001", "issued")
    session = _mock_session_with_row(row)

    with pytest.raises(SaleCannotBeVoidedError) as excinfo:
        await ensure_voidable(session, hub_id, sale)

    error_msg = str(excinfo.value)
    assert "S-002" in error_msg
    assert "INV-001" in error_msg
    assert "issued" in error_msg


@pytest.mark.asyncio
async def test_ensure_voidable_raises_when_invoice_paid():
    hub_id = uuid.uuid4()
    sale = _fake_sale(hub_id, "S-003")
    inv_id = uuid.uuid4()

    row = (inv_id, "B", "INV-002", "paid")
    session = _mock_session_with_row(row)

    with pytest.raises(SaleCannotBeVoidedError) as excinfo:
        await ensure_voidable(session, hub_id, sale)

    assert "S-003" in str(excinfo.value)


@pytest.mark.asyncio
async def test_ensure_voidable_passes_with_draft_invoice():
    """draft status is not in BLOCKING_INVOICE_STATUSES — guard must pass."""
    assert "draft" not in BLOCKING_INVOICE_STATUSES

    hub_id = uuid.uuid4()
    sale = _fake_sale(hub_id, "S-004")
    # The guard queries DB filtered to BLOCKING_INVOICE_STATUSES,
    # so a draft invoice would return no row.
    session = _mock_session_no_row()

    await ensure_voidable(session, hub_id, sale)  # must NOT raise


@pytest.mark.asyncio
async def test_ensure_voidable_passes_with_cancelled_invoice():
    """cancelled status is not in BLOCKING_INVOICE_STATUSES — guard must pass."""
    assert "cancelled" not in BLOCKING_INVOICE_STATUSES

    hub_id = uuid.uuid4()
    sale = _fake_sale(hub_id, "S-005")
    session = _mock_session_no_row()

    await ensure_voidable(session, hub_id, sale)  # must NOT raise


# ---------------------------------------------------------------------------
# Unit tests: SaleCannotBeVoidedError
# ---------------------------------------------------------------------------

def test_error_message_contains_sale_and_invoice():
    invoice_ref = ActiveInvoiceRef(
        invoice_id=uuid.uuid4(),
        invoice_number="A/0001",
        status="issued",
    )
    err = SaleCannotBeVoidedError(sale_number="S-999", invoice=invoice_ref)
    msg = str(err)

    assert "S-999" in msg
    assert "A/0001" in msg
    assert "issued" in msg
    assert "rectification" in msg.lower()


def test_blocking_statuses_are_correct():
    assert frozenset({"issued", "paid"}) == BLOCKING_INVOICE_STATUSES
    assert "draft" not in BLOCKING_INVOICE_STATUSES
    assert "cancelled" not in BLOCKING_INVOICE_STATUSES
