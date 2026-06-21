"""Unit tests for invoice total computation (the money math)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from invoice_generator.model import Invoice


def make_invoice(**overrides):
    data = {
        "number": "T-1",
        "currency": "USD",
        "seller": {"name": "Seller Co"},
        "client": {"name": "Client Co"},
        "items": [{"description": "Item", "quantity": 1, "unit_price": "10.00"}],
    }
    data.update(overrides)
    return Invoice.from_mapping(data)


def test_simple_single_item_no_tax_no_discount():
    inv = make_invoice(
        items=[{"description": "Widget", "quantity": 3, "unit_price": "9.99"}]
    )
    t = inv.compute_totals()
    assert t.subtotal.amount == Decimal("29.97")
    assert t.discount.amount == Decimal("0.00")
    assert t.tax.amount == Decimal("0.00")
    assert t.grand_total.amount == Decimal("29.97")
    assert t.grand_total.format() == "$29.97"


def test_tax_only_rounds_half_up():
    # 100.00 @ 8.875% = 8.875 -> 8.88 (HALF_UP)
    inv = make_invoice(
        items=[{"description": "Service", "quantity": 1, "unit_price": "100.00"}],
        tax_rate="8.875",
    )
    t = inv.compute_totals()
    assert t.subtotal.amount == Decimal("100.00")
    assert t.tax.amount == Decimal("8.88")
    assert t.grand_total.amount == Decimal("108.88")


def test_multi_item_taxed_and_discounted():
    """The headline case: many lines, percentage discount, then tax."""
    inv = make_invoice(
        currency="USD",
        items=[
            {"description": "Discovery & UX", "quantity": 32, "unit_price": "125.00"},
            {"description": "Front-end", "quantity": 48, "unit_price": "110.00"},
            {"description": "CMS integration", "quantity": 1, "unit_price": "2400.00"},
            {"description": "A11y audit", "quantity": 1, "unit_price": "850.00"},
        ],
        discount={"percent": 10},
        tax_rate="8.875",
    )
    t = inv.compute_totals()
    # 4000 + 5280 + 2400 + 850 = 12530
    assert t.subtotal.amount == Decimal("12530.00")
    # 10% of 12530 = 1253.00
    assert t.discount.amount == Decimal("1253.00")
    # base = 11277.00
    assert t.taxable_base.amount == Decimal("11277.00")
    # 8.875% of 11277 = 1000.83375 -> 1000.83
    assert t.tax.amount == Decimal("1000.83")
    # grand = 12277.83
    assert t.grand_total.amount == Decimal("12277.83")
    assert t.grand_total.format() == "$12,277.83"


def test_fixed_amount_discount():
    inv = make_invoice(
        items=[
            {"description": "A", "quantity": 2, "unit_price": "1500.00"},
            {"description": "B", "quantity": 1, "unit_price": "750.00"},
        ],
        discount={"amount": "250.00"},
        tax_rate="0",
    )
    t = inv.compute_totals()
    assert t.subtotal.amount == Decimal("3750.00")
    assert t.discount.amount == Decimal("250.00")
    assert t.grand_total.amount == Decimal("3500.00")


def test_bare_number_discount_is_percent():
    inv = make_invoice(
        items=[{"description": "X", "quantity": 1, "unit_price": "200.00"}],
        discount=20,
    )
    t = inv.compute_totals()
    assert t.discount.amount == Decimal("40.00")
    assert t.grand_total.amount == Decimal("160.00")


def test_discount_clamped_to_subtotal():
    # A discount bigger than the subtotal cannot make the total negative.
    inv = make_invoice(
        items=[{"description": "X", "quantity": 1, "unit_price": "50.00"}],
        discount={"amount": "999.00"},
        tax_rate="10",
    )
    t = inv.compute_totals()
    assert t.discount.amount == Decimal("50.00")
    assert t.taxable_base.amount == Decimal("0.00")
    assert t.tax.amount == Decimal("0.00")
    assert t.grand_total.amount == Decimal("0.00")


def test_jpy_invoice_whole_yen():
    inv = make_invoice(
        currency="JPY",
        items=[
            {"description": "Logo", "quantity": 1, "unit_price": 180000},
            {"description": "Cards", "quantity": 3, "unit_price": 12000},
        ],
        discount={"percent": 5},
        tax_rate=10,
    )
    t = inv.compute_totals()
    # 180000 + 36000 = 216000
    assert t.subtotal.amount == Decimal("216000")
    # 5% = 10800
    assert t.discount.amount == Decimal("10800")
    # base 205200 ; 10% = 20520
    assert t.tax.amount == Decimal("20520")
    assert t.grand_total.amount == Decimal("225720")
    assert t.grand_total.format() == "¥225,720"


def test_fractional_quantity():
    # 2.5 hours @ 80.00 = 200.00
    inv = make_invoice(
        items=[{"description": "Consulting", "quantity": "2.5", "unit_price": "80.00"}]
    )
    t = inv.compute_totals()
    assert t.subtotal.amount == Decimal("200.00")


def test_per_line_rounding_then_sum():
    # Each line rounds before summing so printed lines reconcile.
    # 3 x 0.333 = 0.999 -> line rounds to 1.00; two such lines = 2.00.
    inv = make_invoice(
        items=[
            {"description": "L1", "quantity": 3, "unit_price": "0.333"},
            {"description": "L2", "quantity": 3, "unit_price": "0.333"},
        ]
    )
    t = inv.compute_totals()
    assert t.subtotal.amount == Decimal("2.00")


def test_currency_override():
    inv = Invoice.from_mapping(
        {
            "number": "T-2",
            "currency": "USD",
            "seller": {"name": "S"},
            "client": {"name": "C"},
            "items": [{"description": "X", "quantity": 1, "unit_price": "10"}],
        },
        currency_override="EUR",
    )
    assert inv.currency == "EUR"
    assert inv.compute_totals().grand_total.format() == "€10.00"


def test_missing_required_fields_raise():
    with pytest.raises(ValueError):
        Invoice.from_mapping({"seller": {"name": "S"}, "client": {"name": "C"}})
    with pytest.raises(ValueError):
        Invoice.from_mapping(
            {
                "number": "X",
                "client": {"name": "C"},
                "items": [{"description": "x", "quantity": 1, "unit_price": 1}],
            }
        )
    with pytest.raises(ValueError):
        # No items.
        Invoice.from_mapping(
            {
                "number": "X",
                "seller": {"name": "S"},
                "client": {"name": "C"},
                "items": [],
            }
        )
