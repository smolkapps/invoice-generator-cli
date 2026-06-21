"""Render an :class:`Invoice` to a clean, professional PDF using reportlab."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import List

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .model import Invoice
from .money import decimals_for, symbol_for

# Palette (kept in sync with the HTML renderer for a consistent look).
_ACCENT = colors.HexColor("#2b50aa")
_INK = colors.HexColor("#1a1a2e")
_MUTED = colors.HexColor("#6b7280")
_LINE = colors.HexColor("#e5e7eb")
_ZEBRA = colors.HexColor("#f7f8fa")


def _styles() -> dict:
    base = getSampleStyleSheet()
    styles = {}
    styles["seller_name"] = ParagraphStyle(
        "seller_name",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=_INK,
        leading=20,
    )
    styles["doc_title"] = ParagraphStyle(
        "doc_title",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=26,
        textColor=_ACCENT,
        alignment=TA_RIGHT,
        leading=28,
    )
    styles["doc_num"] = ParagraphStyle(
        "doc_num",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=_MUTED,
        alignment=TA_RIGHT,
        leading=13,
    )
    styles["label"] = ParagraphStyle(
        "label",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        textColor=_MUTED,
        leading=11,
        spaceAfter=2,
    )
    styles["party_name"] = ParagraphStyle(
        "party_name",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        textColor=_INK,
        leading=14,
    )
    styles["party_line"] = ParagraphStyle(
        "party_line",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=_MUTED,
        leading=12,
    )
    styles["meta_k"] = ParagraphStyle(
        "meta_k",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=_MUTED,
        alignment=TA_RIGHT,
        leading=12,
    )
    styles["meta_v"] = ParagraphStyle(
        "meta_v",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=_INK,
        alignment=TA_RIGHT,
        leading=12,
    )
    styles["th"] = ParagraphStyle(
        "th",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=_MUTED,
        leading=11,
    )
    styles["th_r"] = ParagraphStyle("th_r", parent=styles["th"], alignment=TA_RIGHT)
    styles["cell"] = ParagraphStyle(
        "cell",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        textColor=_INK,
        leading=13,
    )
    styles["cell_r"] = ParagraphStyle(
        "cell_r", parent=styles["cell"], alignment=TA_RIGHT
    )
    styles["tot_k"] = ParagraphStyle(
        "tot_k",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        textColor=_MUTED,
        alignment=TA_RIGHT,
        leading=14,
    )
    styles["tot_v"] = ParagraphStyle(
        "tot_v",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        textColor=_INK,
        alignment=TA_RIGHT,
        leading=14,
    )
    styles["grand_k"] = ParagraphStyle(
        "grand_k",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=_INK,
        alignment=TA_RIGHT,
        leading=16,
    )
    styles["grand_v"] = ParagraphStyle(
        "grand_v",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=_ACCENT,
        alignment=TA_RIGHT,
        leading=16,
    )
    styles["note_body"] = ParagraphStyle(
        "note_body",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=_INK,
        leading=12,
    )
    styles["footer"] = ParagraphStyle(
        "footer",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=_MUTED,
        alignment=1,  # center
        leading=11,
    )
    return styles


def _fmt_qty(qty) -> str:
    return format(qty.normalize(), "f")


def _money_paragraph(text: str, style) -> Paragraph:
    return Paragraph(text, style)


def build_story(invoice: Invoice, styles: dict) -> List:
    cur = invoice.currency
    sym = symbol_for(cur)
    places = decimals_for(cur)
    totals = invoice.compute_totals()
    story: List = []

    # ---- Header: seller name (left) + INVOICE title/number (right) ----
    header_tbl = Table(
        [
            [
                Paragraph(invoice.seller.name, styles["seller_name"]),
                [
                    Paragraph("INVOICE", styles["doc_title"]),
                    Paragraph(f"#{invoice.number}", styles["doc_num"]),
                ],
            ]
        ],
        colWidths=[3.3 * inch, 3.2 * inch],
    )
    header_tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, 0), (-1, -1), 2, _ACCENT),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(header_tbl)
    story.append(Spacer(1, 16))

    # ---- Parties + meta ----
    seller_cell = _party_cell(invoice.seller, "FROM", styles)
    client_cell = _party_cell(invoice.client, "BILL TO", styles)
    meta_cell = _meta_cell(invoice, styles)
    parties_tbl = Table(
        [[seller_cell, client_cell, meta_cell]],
        colWidths=[2.5 * inch, 2.3 * inch, 1.7 * inch],
    )
    parties_tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (-1, 0), (-1, 0), 0),
            ]
        )
    )
    story.append(parties_tbl)
    story.append(Spacer(1, 18))

    # ---- Item table ----
    head = [
        Paragraph("DESCRIPTION", styles["th"]),
        Paragraph("QTY", styles["th_r"]),
        Paragraph("UNIT PRICE", styles["th_r"]),
        Paragraph("AMOUNT", styles["th_r"]),
    ]
    data = [head]
    for it in invoice.items:
        line = it.line_total(cur)
        unit_str = f"{sym}{it.unit_price:,.{places}f}"
        data.append(
            [
                Paragraph(it.description, styles["cell"]),
                Paragraph(_fmt_qty(it.quantity), styles["cell_r"]),
                Paragraph(unit_str, styles["cell_r"]),
                Paragraph(line.format(), styles["cell_r"]),
            ]
        )
    item_tbl = Table(
        data,
        colWidths=[3.3 * inch, 0.75 * inch, 1.2 * inch, 1.25 * inch],
        repeatRows=1,
    )
    style_cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, _LINE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, _LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (0, -1), 2),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 2),
    ]
    # Zebra striping on body rows.
    for ridx in range(1, len(data)):
        if ridx % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, ridx), (-1, ridx), _ZEBRA))
    item_tbl.setStyle(TableStyle(style_cmds))
    story.append(item_tbl)
    story.append(Spacer(1, 10))

    # ---- Totals block (right-aligned) ----
    tot_rows = [_kv("Subtotal", totals.subtotal.format(), styles)]
    if totals.discount.amount != 0:
        label = "Discount"
        if invoice.discount and invoice.discount.percent is not None:
            label = f"Discount ({_fmt_qty(invoice.discount.percent)}%)"
        if invoice.discount and invoice.discount.label:
            label = invoice.discount.label
        tot_rows.append(_kv(label, "-" + totals.discount.format(), styles))
    if invoice.tax_rate != 0 or totals.tax.amount != 0:
        tot_rows.append(
            _kv(f"Tax ({_fmt_qty(invoice.tax_rate)}%)", totals.tax.format(), styles)
        )
    tot_rows.append(
        _kv(
            "Total Due",
            totals.grand_total.format(),
            styles,
            grand=True,
        )
    )

    inner = Table(tot_rows, colWidths=[1.6 * inch, 1.4 * inch])
    inner_cmds = [
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 2),
    ]
    grand_idx = len(tot_rows) - 1
    inner_cmds.append(("LINEABOVE", (0, grand_idx), (-1, grand_idx), 1.5, _INK))
    inner_cmds.append(("TOPPADDING", (0, grand_idx), (-1, grand_idx), 7))
    inner.setStyle(TableStyle(inner_cmds))

    totals_wrap = Table([["", inner]], colWidths=[3.45 * inch, 3.0 * inch])
    totals_wrap.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(totals_wrap)

    # ---- Notes / terms ----
    if invoice.notes or invoice.terms:
        story.append(Spacer(1, 26))
        note_cols = []
        if invoice.notes:
            note_cols.append(
                [
                    Paragraph("NOTES", styles["label"]),
                    Paragraph(invoice.notes, styles["note_body"]),
                ]
            )
        if invoice.terms:
            note_cols.append(
                [
                    Paragraph("TERMS", styles["label"]),
                    Paragraph(invoice.terms, styles["note_body"]),
                ]
            )
        if len(note_cols) == 1:
            note_cols.append("")
        notes_tbl = Table([note_cols], colWidths=[3.25 * inch, 3.25 * inch])
        notes_tbl.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (0, 0), 0),
                    ("LINEABOVE", (0, 0), (-1, 0), 0.5, _LINE),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                ]
            )
        )
        story.append(notes_tbl)

    return story


def _party_cell(party, role: str, styles: dict) -> List:
    flow: List = [
        Paragraph(role, styles["label"]),
        Paragraph(party.name, styles["party_name"]),
    ]
    for attr in ("address", "email", "phone"):
        val = getattr(party, attr)
        if val:
            # Address may contain newlines; convert to <br/>.
            text = val.replace("\n", "<br/>")
            flow.append(Paragraph(text, styles["party_line"]))
    return flow


def _meta_cell(invoice: Invoice, styles: dict) -> Table:
    rows = []
    if invoice.issue_date:
        rows.append(
            [
                Paragraph("Issue date", styles["meta_k"]),
                Paragraph(invoice.issue_date, styles["meta_v"]),
            ]
        )
    if invoice.due_date:
        rows.append(
            [
                Paragraph("Due date", styles["meta_k"]),
                Paragraph(invoice.due_date, styles["meta_v"]),
            ]
        )
    rows.append(
        [
            Paragraph("Currency", styles["meta_k"]),
            Paragraph(invoice.currency, styles["meta_v"]),
        ]
    )
    t = Table(rows, colWidths=[0.95 * inch, 0.75 * inch])
    t.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
            ]
        )
    )
    return t


def _kv(label: str, value: str, styles: dict, *, grand: bool = False) -> List:
    if grand:
        return [
            Paragraph(label, styles["grand_k"]),
            Paragraph(value, styles["grand_v"]),
        ]
    return [Paragraph(label, styles["tot_k"]), Paragraph(value, styles["tot_v"])]


def _footer(canvas, doc) -> None:
    canvas.saveState()
    styles = _styles()
    p = Paragraph("Thank you for your business.", styles["footer"])
    w, h = p.wrap(doc.width, 0.5 * inch)
    p.drawOn(canvas, doc.leftMargin, 0.55 * inch)
    canvas.restoreState()


def render_pdf_bytes(invoice: Invoice) -> bytes:
    """Render the invoice and return the PDF as bytes."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.9 * inch,
        title=f"Invoice {invoice.number}",
        author=invoice.seller.name,
    )
    styles = _styles()
    story = build_story(invoice, styles)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def render_pdf(invoice: Invoice, path: str | Path) -> Path:
    """Render the invoice to a PDF file at ``path``; return the path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(render_pdf_bytes(invoice))
    return out
