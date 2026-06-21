"""Exact money handling using :class:`decimal.Decimal`.

Money is *never* represented as a binary float. All arithmetic is done with
``Decimal`` and rounded with ``ROUND_HALF_UP`` (the rounding rule people expect
on invoices) to the currency's minor-unit precision.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Mapping


# Number of decimal places (minor units) per ISO-4217 currency code.
# Anything not listed defaults to 2.
_CURRENCY_DECIMALS: Mapping[str, int] = {
    "JPY": 0,
    "KRW": 0,
    "CLP": 0,
    "ISK": 0,
    "HUF": 0,  # technically 2, but commonly priced as whole forint
    "VND": 0,
    "BHD": 3,
    "KWD": 3,
    "OMR": 3,
    "TND": 3,
}

# Display symbol per currency code. Falls back to "<CODE> " (e.g. "AUD ").
_CURRENCY_SYMBOLS: Mapping[str, str] = {
    "USD": "$",
    "CAD": "$",
    "AUD": "$",
    "NZD": "$",
    "HKD": "$",
    "SGD": "$",
    "MXN": "$",
    "EUR": "€",  # €
    "GBP": "£",  # £
    "JPY": "¥",  # ¥
    "CNY": "¥",  # ¥
    "INR": "₹",  # ₹
    "KRW": "₩",  # ₩
    "RUB": "₽",  # ₽
    "BRL": "R$",
    "CHF": "CHF ",
    "ZAR": "R",
    "PLN": "zł",
    "SEK": "kr",
    "NOK": "kr",
    "DKK": "kr",
    "TRY": "₺",  # ₺
    "ILS": "₪",  # ₪
    "THB": "฿",  # ฿
}


def decimals_for(currency: str) -> int:
    """Return the number of minor-unit decimal places for a currency code."""
    return _CURRENCY_DECIMALS.get(currency.upper(), 2)


def symbol_for(currency: str) -> str:
    """Return a display symbol for a currency code.

    Falls back to ``"<CODE> "`` (code plus a trailing space) for unknown codes
    so output is still unambiguous.
    """
    code = currency.upper()
    return _CURRENCY_SYMBOLS.get(code, f"{code} ")


def to_decimal(value: object) -> Decimal:
    """Coerce an arbitrary scalar into a ``Decimal`` safely.

    Floats are routed through ``repr`` first so e.g. ``0.1`` becomes
    ``Decimal("0.1")`` rather than the full binary-expansion noise.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):  # bool is an int subclass; reject explicitly
        raise TypeError("boolean is not a valid monetary value")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if text == "":
            raise ValueError("empty string is not a valid monetary value")
        try:
            return Decimal(text)
        except InvalidOperation as exc:  # pragma: no cover - re-raise clean
            raise ValueError(f"cannot parse {value!r} as a number") from exc
    raise TypeError(f"unsupported monetary value type: {type(value).__name__}")


def quantize(amount: Decimal, currency: str) -> Decimal:
    """Round ``amount`` to the currency's minor-unit precision, HALF_UP."""
    places = decimals_for(currency)
    if places == 0:
        exp = Decimal(1)
    else:
        exp = Decimal(1).scaleb(-places)  # e.g. places=2 -> Decimal("0.01")
    return amount.quantize(exp, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Money:
    """An exact monetary amount tied to a currency.

    The stored ``amount`` is always quantized to the currency precision.
    """

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        # Normalize: enforce Decimal type and quantize on construction.
        object.__setattr__(self, "currency", self.currency.upper())
        object.__setattr__(
            self, "amount", quantize(to_decimal(self.amount), self.currency)
        )

    @classmethod
    def of(cls, value: object, currency: str) -> "Money":
        return cls(to_decimal(value), currency)

    def format(self, *, symbol: bool = True) -> str:
        """Render as a human string, e.g. ``"$1,234.50"`` or ``"1,234.50"``.

        Negative amounts are rendered as ``-$1.00`` (sign before the symbol).
        Thousands separators are inserted; the fractional part matches the
        currency precision.
        """
        places = decimals_for(self.currency)
        negative = self.amount < 0
        magnitude = -self.amount if negative else self.amount
        # Render with fixed places and grouping via Python format spec.
        as_float_str = f"{magnitude:,.{places}f}"
        sym = symbol_for(self.currency) if symbol else ""
        sign = "-" if negative else ""
        return f"{sign}{sym}{as_float_str}"

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.format()
