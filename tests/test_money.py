"""Unit tests for exact Decimal money handling."""

from __future__ import annotations

from decimal import Decimal

import pytest

from invoice_generator.money import (
    Money,
    decimals_for,
    quantize,
    symbol_for,
    to_decimal,
)


def test_float_does_not_introduce_binary_noise():
    # 0.1 + 0.2 in float is 0.30000000000000004; via Decimal repr it's exact.
    assert to_decimal(0.1) == Decimal("0.1")
    m = Money(Decimal("0.1"), "USD")
    n = Money(Decimal("0.2"), "USD")
    total = Money(m.amount + n.amount, "USD")
    assert total.amount == Decimal("0.30")
    assert total.format() == "$0.30"


def test_quantize_half_up():
    # 2.675 should round to 2.68 (HALF_UP), not 2.67 (banker's/float).
    assert quantize(Decimal("2.675"), "USD") == Decimal("2.68")
    assert quantize(Decimal("1.005"), "USD") == Decimal("1.01")


def test_currency_precision():
    assert decimals_for("USD") == 2
    assert decimals_for("JPY") == 0
    assert decimals_for("BHD") == 3
    # JPY has no minor unit: 1234.6 rounds to 1235.
    assert Money(Decimal("1234.6"), "JPY").amount == Decimal("1235")
    # 3-decimal currency keeps three places (HALF_UP: 1.2345 -> 1.235).
    assert Money(Decimal("1.2345"), "BHD").amount == Decimal("1.235")


def test_jpy_formatting_no_decimals():
    assert Money(Decimal("180000"), "JPY").format() == "¥180,000"


def test_symbols():
    assert symbol_for("USD") == "$"
    assert symbol_for("EUR") == "€"
    assert symbol_for("GBP") == "£"
    assert symbol_for("JPY") == "¥"
    # Unknown code falls back to "<CODE> ".
    assert symbol_for("XYZ") == "XYZ "


def test_thousands_separator_and_sign():
    assert Money(Decimal("1234567.5"), "USD").format() == "$1,234,567.50"
    assert Money(Decimal("-50"), "USD").format() == "-$50.00"
    assert Money(Decimal("1000"), "EUR").format() == "€1,000.00"


def test_string_input_with_commas():
    assert to_decimal("1,234.50") == Decimal("1234.50")


def test_bool_rejected():
    with pytest.raises(TypeError):
        to_decimal(True)


def test_money_is_quantized_on_construction():
    # Passing more precision than the currency supports rounds immediately.
    m = Money(Decimal("9.999"), "USD")
    assert m.amount == Decimal("10.00")
