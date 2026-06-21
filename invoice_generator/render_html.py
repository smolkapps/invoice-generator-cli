"""Render an :class:`Invoice` to a standalone, styled HTML document."""

from __future__ import annotations

from html import escape
from typing import List, Optional

from .model import Invoice
from .money import symbol_for


def _row(
    cells: List[str], *, tag: str = "td", classes: Optional[List[str]] = None
) -> str:
    out = []
    for i, c in enumerate(cells):
        cls = ""
        if classes and i < len(classes) and classes[i]:
            cls = f' class="{classes[i]}"'
        out.append(f"<{tag}{cls}>{c}</{tag}>")
    return "<tr>" + "".join(out) + "</tr>"


def _fmt_qty(qty) -> str:
    # Show integers cleanly (2 not 2.00) but keep fractional quantities.
    normalized = qty.normalize()
    text = format(normalized, "f")
    return text


def render_html(invoice: Invoice) -> str:
    """Return a complete HTML document (``<!doctype html> ...``) as a string."""
    totals = invoice.compute_totals()
    cur = invoice.currency
    sym = symbol_for(cur)

    def money(m) -> str:
        return escape(m.format())

    # --- item rows ---
    item_rows: List[str] = []
    for it in invoice.items:
        line = it.line_total(cur)
        item_rows.append(
            _row(
                [
                    escape(it.description),
                    _fmt_qty(it.quantity),
                    f"{escape(sym)}{it.unit_price:,.{_decimals(cur)}f}",
                    money(line),
                ],
                classes=["desc", "num", "num", "num"],
            )
        )
    items_html = "\n".join(item_rows)

    # --- totals rows ---
    totals_rows: List[str] = []
    totals_rows.append(_total_line("Subtotal", money(totals.subtotal)))
    if totals.discount.amount != 0:
        label = "Discount"
        if invoice.discount and invoice.discount.percent is not None:
            label = f"Discount ({_fmt_qty(invoice.discount.percent)}%)"
        if invoice.discount and invoice.discount.label:
            label = escape(invoice.discount.label)
        totals_rows.append(_total_line(label, "-" + money(totals.discount)))
    if invoice.tax_rate != 0 or totals.tax.amount != 0:
        totals_rows.append(
            _total_line(f"Tax ({_fmt_qty(invoice.tax_rate)}%)", money(totals.tax))
        )
    totals_rows.append(_total_line("Total Due", money(totals.grand_total), grand=True))
    totals_html = "\n".join(totals_rows)

    seller = _party_block(invoice.seller, "From")
    client = _party_block(invoice.client, "Bill To")

    meta_rows = []
    if invoice.issue_date:
        meta_rows.append(_meta_row("Issue date", escape(invoice.issue_date)))
    if invoice.due_date:
        meta_rows.append(_meta_row("Due date", escape(invoice.due_date)))
    meta_rows.append(_meta_row("Currency", escape(cur)))
    meta_html = "\n".join(meta_rows)

    notes_section = ""
    if invoice.notes or invoice.terms:
        parts = []
        if invoice.notes:
            parts.append(
                f'<div class="note"><h3>Notes</h3><p>{escape(invoice.notes)}</p></div>'
            )
        if invoice.terms:
            parts.append(
                f'<div class="note"><h3>Terms</h3><p>{escape(invoice.terms)}</p></div>'
            )
        notes_section = f'<section class="notes">{"".join(parts)}</section>'

    title = f"Invoice {escape(invoice.number)}"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{
    --ink: #1a1a2e;
    --muted: #6b7280;
    --line: #e5e7eb;
    --accent: #2b50aa;
    --bg: #f4f5f7;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: var(--ink);
    background: var(--bg);
    margin: 0;
    padding: 2rem;
    line-height: 1.45;
  }}
  .invoice {{
    max-width: 800px;
    margin: 0 auto;
    background: #fff;
    padding: 3rem;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,.08), 0 8px 24px rgba(0,0,0,.06);
  }}
  header.top {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    border-bottom: 3px solid var(--accent);
    padding-bottom: 1.25rem;
    margin-bottom: 1.5rem;
  }}
  .brand h1 {{ margin: 0; font-size: 1.4rem; }}
  .doc-title {{ text-align: right; }}
  .doc-title h2 {{
    margin: 0; font-size: 2rem; letter-spacing: .04em;
    text-transform: uppercase; color: var(--accent);
  }}
  .doc-title .num {{ color: var(--muted); font-size: .95rem; margin-top: .25rem; }}
  .parties {{
    display: flex; gap: 2rem; margin-bottom: 1.5rem; flex-wrap: wrap;
  }}
  .parties .col {{ flex: 1 1 220px; }}
  .parties h3 {{
    margin: 0 0 .35rem; font-size: .72rem; letter-spacing: .08em;
    text-transform: uppercase; color: var(--muted);
  }}
  .parties .name {{ font-weight: 600; }}
  .parties .lines {{ color: var(--muted); font-size: .9rem; white-space: pre-line; }}
  table.meta {{ margin-left: auto; border-collapse: collapse; font-size: .9rem; }}
  table.meta td {{ padding: .15rem 0; }}
  table.meta td.k {{ color: var(--muted); padding-right: 1rem; text-align: right; }}
  table.items {{
    width: 100%; border-collapse: collapse; margin: 1rem 0 0;
  }}
  table.items thead th {{
    text-align: left; font-size: .72rem; letter-spacing: .06em;
    text-transform: uppercase; color: var(--muted);
    border-bottom: 2px solid var(--line); padding: .5rem .5rem;
  }}
  table.items tbody td {{
    padding: .6rem .5rem; border-bottom: 1px solid var(--line);
    vertical-align: top;
  }}
  table.items .num, table.items th.num {{ text-align: right; }}
  table.items .desc {{ width: 55%; }}
  .totals {{ width: 100%; display: flex; justify-content: flex-end; margin-top: 1rem; }}
  table.totals-table {{ border-collapse: collapse; min-width: 280px; }}
  table.totals-table td {{ padding: .35rem .5rem; }}
  table.totals-table td.k {{ color: var(--muted); text-align: right; }}
  table.totals-table td.v {{ text-align: right; font-variant-numeric: tabular-nums; }}
  table.totals-table tr.grand td {{
    border-top: 2px solid var(--ink); font-weight: 700; font-size: 1.15rem;
    padding-top: .6rem;
  }}
  table.totals-table tr.grand td.v {{ color: var(--accent); }}
  .notes {{ margin-top: 2rem; display: flex; gap: 2rem; flex-wrap: wrap; }}
  .notes .note {{ flex: 1 1 240px; }}
  .notes h3 {{
    margin: 0 0 .3rem; font-size: .72rem; letter-spacing: .08em;
    text-transform: uppercase; color: var(--muted);
  }}
  .notes p {{ margin: 0; color: var(--ink); font-size: .9rem; }}
  footer.foot {{
    margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid var(--line);
    text-align: center; color: var(--muted); font-size: .8rem;
  }}
  @media print {{
    body {{ background: #fff; padding: 0; }}
    .invoice {{ box-shadow: none; border-radius: 0; }}
  }}
</style>
</head>
<body>
<div class="invoice">
  <header class="top">
    <div class="brand">
      <h1>{escape(invoice.seller.name)}</h1>
    </div>
    <div class="doc-title">
      <h2>Invoice</h2>
      <div class="num">#{escape(invoice.number)}</div>
    </div>
  </header>

  <div class="parties">
    <div class="col">{seller}</div>
    <div class="col">{client}</div>
    <table class="meta">
{meta_html}
    </table>
  </div>

  <table class="items">
    <thead>
      <tr>
        <th class="desc">Description</th>
        <th class="num">Qty</th>
        <th class="num">Unit Price</th>
        <th class="num">Amount</th>
      </tr>
    </thead>
    <tbody>
{items_html}
    </tbody>
  </table>

  <div class="totals">
    <table class="totals-table">
{totals_html}
    </table>
  </div>

  {notes_section}

  <footer class="foot">
    Thank you for your business.
  </footer>
</div>
</body>
</html>
"""


def _decimals(currency: str) -> int:
    from .money import decimals_for

    return decimals_for(currency)


def _total_line(label: str, value: str, *, grand: bool = False) -> str:
    cls = ' class="grand"' if grand else ""
    return f'<tr{cls}><td class="k">{label}</td><td class="v">{value}</td></tr>'


def _meta_row(key: str, value: str) -> str:
    return f'<tr><td class="k">{key}</td><td class="v">{value}</td></tr>'


def _party_block(party, role: str) -> str:
    lines = []
    if party.address:
        lines.append(escape(party.address))
    if party.email:
        lines.append(escape(party.email))
    if party.phone:
        lines.append(escape(party.phone))
    detail = "\n".join(lines)
    return (
        f"<h3>{escape(role)}</h3>"
        f'<div class="name">{escape(party.name)}</div>'
        f'<div class="lines">{detail}</div>'
    )
