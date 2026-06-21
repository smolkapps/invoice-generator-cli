"""Tests for PDF and HTML rendering, incl. round-trip text extraction."""

from __future__ import annotations

import io
from decimal import Decimal

import pytest

from invoice_generator.model import Invoice
from invoice_generator.render_html import render_html
from invoice_generator.render_pdf import render_pdf, render_pdf_bytes

pypdf = pytest.importorskip("pypdf")


SAMPLE = {
    "number": "INV-2026-0042",
    "issue_date": "2026-06-21",
    "due_date": "2026-07-21",
    "currency": "USD",
    "seller": {
        "name": "Acme Web Studio LLC",
        "address": "123 Market Street\nSan Francisco, CA 94103",
        "email": "billing@acmewebstudio.example",
    },
    "client": {
        "name": "Globex Corporation",
        "address": "500 Enterprise Way\nMetropolis, NY 10001",
    },
    "items": [
        {"description": "Discovery & UX", "quantity": 32, "unit_price": "125.00"},
        {
            "description": "Front-end implementation",
            "quantity": 48,
            "unit_price": "110.00",
        },
        {"description": "CMS integration", "quantity": 1, "unit_price": "2400.00"},
        {"description": "Accessibility audit", "quantity": 1, "unit_price": "850.00"},
    ],
    "discount": {"percent": 10, "label": "Returning client"},
    "tax_rate": "8.875",
    "notes": "Deposit invoiced separately.",
    "terms": "Net 30.",
}

EXPECTED_GRAND = "$12,277.83"


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_pdf_is_valid_and_contains_key_fields():
    inv = Invoice.from_mapping(SAMPLE)
    pdf_bytes = render_pdf_bytes(inv)
    # Valid PDF magic header.
    assert pdf_bytes[:5] == b"%PDF-"
    assert b"%%EOF" in pdf_bytes[-1024:]

    text = _extract_pdf_text(pdf_bytes)
    # Invoice number present.
    assert "INV-2026-0042" in text
    # Client name present.
    assert "Globex Corporation" in text
    # Seller name present.
    assert "Acme Web Studio LLC" in text
    # Correctly-computed grand total string present.
    assert EXPECTED_GRAND in text


def test_pdf_contains_computed_tax_and_subtotal():
    inv = Invoice.from_mapping(SAMPLE)
    text = _extract_pdf_text(render_pdf_bytes(inv))
    assert "$12,530.00" in text  # subtotal
    assert "$1,253.00" in text  # discount
    assert "$1,000.83" in text  # tax


def test_pdf_written_to_disk(tmp_path):
    inv = Invoice.from_mapping(SAMPLE)
    out = tmp_path / "invoice.pdf"
    returned = render_pdf(inv, out)
    assert returned == out
    assert out.exists()
    data = out.read_bytes()
    assert data[:5] == b"%PDF-"
    assert EXPECTED_GRAND in _extract_pdf_text(data)


def test_html_contains_same_totals():
    inv = Invoice.from_mapping(SAMPLE)
    html = render_html(inv)
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert "INV-2026-0042" in html
    assert "Globex Corporation" in html
    assert "Acme Web Studio LLC" in html
    # Same computed totals as the PDF.
    assert EXPECTED_GRAND in html
    assert "$12,530.00" in html  # subtotal
    assert "$1,253.00" in html  # discount
    assert "$1,000.83" in html  # tax


def test_html_is_self_contained():
    # No external CSS/JS references — fully standalone page.
    inv = Invoice.from_mapping(SAMPLE)
    html = render_html(inv)
    assert "<style>" in html
    assert "<link" not in html
    assert "<script" not in html


def test_html_escapes_user_content():
    data = {**SAMPLE, "client": {"name": "Evil <script>alert(1)</script> & Co"}}
    html = render_html(Invoice.from_mapping(data))
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html


def test_jpy_pdf_and_html_totals():
    data = {
        "number": "INV-JP-1",
        "currency": "JPY",
        "seller": {"name": "Sakura Design Co."},
        "client": {"name": "Yoyodyne KK"},
        "items": [
            {"description": "Logo", "quantity": 1, "unit_price": 180000},
            {"description": "Cards", "quantity": 3, "unit_price": 12000},
        ],
        "discount": {"percent": 5},
        "tax_rate": 10,
    }
    inv = Invoice.from_mapping(data)
    assert inv.compute_totals().grand_total.format() == "¥225,720"
    html = render_html(inv)
    assert "¥225,720" in html
    text = _extract_pdf_text(render_pdf_bytes(inv))
    # The yen symbol may not extract cleanly from the PDF font, so assert on the
    # digit grouping which is font-independent.
    assert "225,720" in text
