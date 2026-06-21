"""Invoice data model and exact (Decimal) total computation.

The model is intentionally plain dataclasses so it can be built either from a
parsed mapping (JSON/YAML/TOML) or directly in code/tests.

Computation order (matches how invoices are conventionally totalled):

    line_total[i] = round(qty[i] * unit_price[i])
    subtotal      = sum(line_total)
    discount      = percentage or fixed amount, applied to subtotal
    taxable_base  = subtotal - discount
    tax           = round(taxable_base * tax_rate%)
    grand_total   = taxable_base + tax

All rounding is to the currency's minor unit, HALF_UP. Each line total is
rounded before summing so the printed lines always add up to the subtotal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping, Optional, Sequence

from .money import Money, quantize, to_decimal

DEFAULT_CURRENCY = "USD"


@dataclass(frozen=True)
class Party:
    """A seller or client. Only ``name`` is required."""

    name: str
    address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Party":
        if not isinstance(data, Mapping):
            raise TypeError("party must be a mapping/object")
        name = data.get("name")
        if not name:
            raise ValueError("party requires a 'name'")
        return cls(
            name=str(name),
            address=_opt_str(data.get("address")),
            email=_opt_str(data.get("email")),
            phone=_opt_str(data.get("phone")),
        )


@dataclass(frozen=True)
class LineItem:
    """A single billable line. Quantity and unit price are Decimals."""

    description: str
    quantity: Decimal
    unit_price: Decimal

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "LineItem":
        if not isinstance(data, Mapping):
            raise TypeError("line item must be a mapping/object")
        description = data.get("description")
        if description is None or str(description).strip() == "":
            raise ValueError("line item requires a 'description'")
        if "quantity" not in data and "qty" not in data:
            raise ValueError(f"line item {description!r} requires a 'quantity'")
        if "unit_price" not in data and "price" not in data:
            raise ValueError(f"line item {description!r} requires a 'unit_price'")
        qty = to_decimal(data.get("quantity", data.get("qty")))
        price = to_decimal(data.get("unit_price", data.get("price")))
        if qty < 0:
            raise ValueError(f"line item {description!r} has negative quantity")
        if price < 0:
            raise ValueError(f"line item {description!r} has negative unit_price")
        return cls(description=str(description), quantity=qty, unit_price=price)

    def raw_total(self) -> Decimal:
        """Un-rounded qty * unit_price."""
        return self.quantity * self.unit_price

    def line_total(self, currency: str) -> Money:
        return Money(self.raw_total(), currency)


@dataclass(frozen=True)
class Discount:
    """A discount applied to the subtotal.

    Exactly one of ``percent`` or ``amount`` is meaningful. ``percent`` is a
    number like ``Decimal("10")`` meaning 10%.
    """

    percent: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    label: Optional[str] = None

    @classmethod
    def from_value(cls, value: Any) -> Optional["Discount"]:
        if value is None:
            return None
        # A bare number is treated as a percentage for convenience.
        if isinstance(value, (int, float, str, Decimal)):
            return cls(percent=to_decimal(value))
        if isinstance(value, Mapping):
            percent = value.get("percent", value.get("percentage"))
            amount = value.get("amount")
            if percent is not None and amount is not None:
                raise ValueError("discount cannot set both 'percent' and 'amount'")
            if percent is None and amount is None:
                return None
            return cls(
                percent=to_decimal(percent) if percent is not None else None,
                amount=to_decimal(amount) if amount is not None else None,
                label=_opt_str(value.get("label")),
            )
        raise TypeError("discount must be a number or an object")

    def compute(self, subtotal: Decimal, currency: str) -> Money:
        """Return the discount value as a positive ``Money`` amount."""
        if self.amount is not None:
            value = self.amount
        elif self.percent is not None:
            value = subtotal * self.percent / Decimal(100)
        else:  # pragma: no cover - constructed only with one set
            value = Decimal(0)
        return Money(value, currency)


@dataclass(frozen=True)
class Totals:
    """Computed, rounded totals for an invoice."""

    subtotal: Money
    discount: Money
    taxable_base: Money
    tax: Money
    grand_total: Money
    tax_rate: Decimal


@dataclass
class Invoice:
    seller: Party
    client: Party
    number: str
    issue_date: Optional[str] = None
    due_date: Optional[str] = None
    currency: str = DEFAULT_CURRENCY
    items: Sequence[LineItem] = field(default_factory=list)
    tax_rate: Decimal = Decimal(0)  # percentage, e.g. Decimal("8.875")
    discount: Optional[Discount] = None
    notes: Optional[str] = None
    terms: Optional[str] = None

    # ----- construction -------------------------------------------------
    @classmethod
    def from_mapping(
        cls, data: Mapping[str, Any], *, currency_override: Optional[str] = None
    ) -> "Invoice":
        if not isinstance(data, Mapping):
            raise TypeError("invoice data must be a mapping/object at the top level")

        if "seller" not in data:
            raise ValueError("invoice requires a 'seller'")
        if "client" not in data:
            raise ValueError("invoice requires a 'client'")
        number = data.get("number", data.get("invoice_number"))
        if number is None or str(number).strip() == "":
            raise ValueError("invoice requires a 'number'")

        raw_items = data.get("items", data.get("line_items", []))
        if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
            raise TypeError("'items' must be a list")
        items = [LineItem.from_mapping(it) for it in raw_items]
        if not items:
            raise ValueError("invoice requires at least one line item")

        currency = currency_override or data.get("currency") or DEFAULT_CURRENCY

        tax_rate = data.get("tax_rate", data.get("tax", 0))
        tax_rate_dec = to_decimal(tax_rate) if tax_rate is not None else Decimal(0)
        if tax_rate_dec < 0:
            raise ValueError("tax_rate cannot be negative")

        return cls(
            seller=Party.from_mapping(data["seller"]),
            client=Party.from_mapping(data["client"]),
            number=str(number),
            issue_date=_opt_str(data.get("issue_date", data.get("date"))),
            due_date=_opt_str(data.get("due_date")),
            currency=str(currency).upper(),
            items=items,
            tax_rate=tax_rate_dec,
            discount=Discount.from_value(data.get("discount")),
            notes=_opt_str(data.get("notes")),
            terms=_opt_str(data.get("terms")),
        )

    # ----- computation --------------------------------------------------
    def compute_totals(self) -> Totals:
        currency = self.currency

        # Round each line before summing so the printed lines reconcile.
        line_rounded = [quantize(it.raw_total(), currency) for it in self.items]
        subtotal_dec = sum(line_rounded, Decimal(0))

        if self.discount is not None:
            discount_money = self.discount.compute(subtotal_dec, currency)
        else:
            discount_money = Money(Decimal(0), currency)
        discount_dec = discount_money.amount

        # Clamp discount so the taxable base never goes negative.
        if discount_dec > subtotal_dec:
            discount_dec = subtotal_dec
            discount_money = Money(discount_dec, currency)

        taxable_dec = subtotal_dec - discount_dec
        tax_dec = quantize(taxable_dec * self.tax_rate / Decimal(100), currency)
        grand_dec = taxable_dec + tax_dec

        return Totals(
            subtotal=Money(subtotal_dec, currency),
            discount=discount_money,
            taxable_base=Money(taxable_dec, currency),
            tax=Money(tax_dec, currency),
            grand_total=Money(grand_dec, currency),
            tax_rate=self.tax_rate,
        )


def _opt_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    return text if text != "" else None
