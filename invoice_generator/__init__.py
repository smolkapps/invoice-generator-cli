"""invoice-generator: turn structured data into a professional invoice PDF/HTML.

Public API:

    from invoice_generator import Invoice, render_pdf, render_html, load_file

All money math is exact (``decimal.Decimal``); nothing touches the network.
"""

from __future__ import annotations

from .loader import detect_format, load_file, load_mapping
from .model import Discount, Invoice, LineItem, Party, Totals
from .money import Money, decimals_for, symbol_for
from .render_html import render_html
from .render_pdf import render_pdf, render_pdf_bytes

__version__ = "1.0.0"

__all__ = [
    "Invoice",
    "Party",
    "LineItem",
    "Discount",
    "Totals",
    "Money",
    "decimals_for",
    "symbol_for",
    "load_file",
    "load_mapping",
    "detect_format",
    "render_pdf",
    "render_pdf_bytes",
    "render_html",
    "__version__",
]
