# invoice-generator

Generate a professional **invoice PDF** (and standalone **HTML**) from structured
data — JSON, YAML, or TOML. Money math is **exact** (`decimal.Decimal`, rounded
HALF-UP to the currency's minor unit), and the tool does **zero network/API
calls** at runtime.

## Features

- Input as **JSON / YAML / TOML** — format inferred from the file extension.
- Clean PDF (via [reportlab](https://www.reportlab.com/)): header with invoice #,
  `FROM` / `BILL TO` blocks, line-item table with zebra striping, a totals block,
  and footer notes/terms.
- Standalone, self-styled **HTML** output (no external CSS/JS).
- Exact **Decimal** money: per-line totals, subtotal, percentage **or** fixed
  **discount**, **tax**, grand total. Each line is rounded before summing so the
  printed lines always reconcile with the subtotal.
- Per-currency symbol and precision (e.g. `$`/2dp, `€`/2dp, `¥`/0dp for JPY,
  3dp for BHD/KWD/OMR). Unknown codes fall back to `CODE ` + 2dp.
- `--currency` override on the command line.

## Install

```bash
pip install -e .          # runtime
pip install -e ".[test]"  # + pytest, pypdf for the test suite
```

Runtime dependencies: **reportlab**, **pyyaml**, and **tomli** (only on Python
< 3.11; 3.11+ uses the stdlib `tomllib`). Requires Python ≥ 3.9.

## Usage

```bash
# Infer output format from the -o extension:
invoice-generator examples/invoice.json -o invoice.pdf
invoice-generator examples/invoice.json -o invoice.html

# Default output is <data>.pdf next to the input:
invoice-generator examples/invoice.json          # -> examples/invoice.pdf

# Force a format regardless of extension, and override the currency:
invoice-generator examples/invoice.yaml -o out.bin --format html
invoice-generator examples/invoice.json -o eur.pdf --currency EUR
```

`invgen` is installed as a short alias for `invoice-generator`.

### Options

| Flag | Meaning |
|------|---------|
| `-o, --output PATH` | Output file. Format inferred from extension (`.pdf` / `.html`). Defaults to `<data>.pdf`. |
| `-f, --format {pdf,html}` | Force output format, overriding the extension. |
| `-c, --currency CODE` | ISO-4217 currency code override (e.g. `USD`, `EUR`, `JPY`). |
| `-q, --quiet` | Suppress the success line. |
| `--version` | Print version and exit. |

## Sample data file

`examples/invoice.json` (a multi-item, discounted, taxed invoice):

```json
{
  "number": "INV-2026-0042",
  "issue_date": "2026-06-21",
  "due_date": "2026-07-21",
  "currency": "USD",
  "seller": {
    "name": "Acme Web Studio LLC",
    "address": "123 Market Street\nSuite 400\nSan Francisco, CA 94103",
    "email": "billing@acmewebstudio.example",
    "phone": "+1 (415) 555-0100"
  },
  "client": {
    "name": "Globex Corporation",
    "address": "500 Enterprise Way\nMetropolis, NY 10001",
    "email": "accounts.payable@globex.example"
  },
  "items": [
    { "description": "Website redesign — discovery & UX", "quantity": 32, "unit_price": 125.00 },
    { "description": "Front-end implementation (per hour)", "quantity": 48, "unit_price": 110.00 },
    { "description": "CMS integration & content migration", "quantity": 1, "unit_price": 2400.00 },
    { "description": "Accessibility audit (WCAG 2.1 AA)", "quantity": 1, "unit_price": 850.00 }
  ],
  "discount": { "percent": 10, "label": "Returning client (10%)" },
  "tax_rate": 8.875,
  "notes": "50% deposit was invoiced separately on 2026-05-15.",
  "terms": "Payment due within 30 days. Late payments accrue 1.5% monthly interest."
}
```

This computes to:

| | |
|---|---:|
| Subtotal | `$12,530.00` |
| Discount (10%) | `-$1,253.00` |
| Tax (8.875%) | `$1,000.83` |
| **Total Due** | **`$12,277.83`** |

YAML and TOML equivalents are in `examples/invoice.yaml` and
`examples/invoice.toml`.

### Schema

Top-level keys:

- `number` (or `invoice_number`) — **required**, string.
- `seller` / `client` — **required** objects. `name` is required; `address`,
  `email`, `phone` optional. `address` may contain `\n` line breaks.
- `items` (or `line_items`) — **required**, non-empty list. Each item:
  `description` (required), `quantity` (or `qty`), `unit_price` (or `price`).
  Quantities may be fractional; values may be numbers or numeric strings.
- `currency` — ISO-4217 code, default `USD`. Overridable with `--currency`.
- `tax_rate` (or `tax`) — percentage, e.g. `8.875`. Default `0`.
- `discount` — either a bare number (treated as a percentage), or an object with
  **one** of `percent` / `amount`, plus an optional `label`.
- `issue_date` (or `date`), `due_date` — free-form strings (shown verbatim).
- `notes`, `terms` — free-form strings shown in the footer.

A discount larger than the subtotal is clamped so the total never goes negative.

## Library API

```python
from invoice_generator import Invoice, load_file, render_pdf, render_html

invoice = Invoice.from_mapping(load_file("examples/invoice.json"))
totals = invoice.compute_totals()
print(totals.grand_total.format())     # "$12,277.83"

render_pdf(invoice, "invoice.pdf")
open("invoice.html", "w").write(render_html(invoice))
```

## Tests

```bash
pip install -e ".[test]"
pytest -q
```

The suite covers the Decimal money math (multiple cases incl. the multi-item
taxed+discounted invoice and a zero-decimal JPY invoice), generates a real PDF
and extracts its text with `pypdf` to assert the invoice number, client name, and
correctly-computed grand total all appear, and checks the HTML output carries the
same totals.

## License

MIT — see [LICENSE](LICENSE).
