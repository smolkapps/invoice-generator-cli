"""Command-line interface for invoice-generator (thin argparse wrapper)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from . import __version__
from .loader import UnsupportedFormatError, load_file
from .model import Invoice
from .render_html import render_html
from .render_pdf import render_pdf

_PDF_EXT = {".pdf"}
_HTML_EXT = {".html", ".htm"}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="invoice-generator",
        description=(
            "Generate a professional invoice PDF or HTML from structured data "
            "(JSON / YAML / TOML). All money math is exact; no network access."
        ),
    )
    p.add_argument("data", help="path to invoice data file (.json/.yaml/.yml/.toml)")
    p.add_argument(
        "-o",
        "--output",
        help="output file path. Format is inferred from its extension "
        "(.pdf/.html) unless --format is given. Defaults to <data>.pdf",
    )
    p.add_argument(
        "-f",
        "--format",
        choices=["pdf", "html"],
        help="output format; overrides extension inference",
    )
    p.add_argument(
        "-c",
        "--currency",
        help="ISO-4217 currency code override (e.g. USD, EUR, JPY)",
    )
    p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="suppress the success message",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return p


def _resolve_format(output: Optional[Path], explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    if output is not None:
        ext = output.suffix.lower()
        if ext in _PDF_EXT:
            return "pdf"
        if ext in _HTML_EXT:
            return "html"
    return "pdf"


def _default_output(data_path: Path, fmt: str) -> Path:
    suffix = ".pdf" if fmt == "pdf" else ".html"
    return data_path.with_suffix(suffix)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    data_path = Path(args.data)
    output_path = Path(args.output) if args.output else None

    # If --format given but no output, derive the default name from format.
    # If output given, its extension drives the format unless --format overrides.
    fmt = _resolve_format(output_path, args.format)
    if output_path is None:
        output_path = _default_output(data_path, fmt)

    try:
        raw = load_file(data_path)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except UnsupportedFormatError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # parse errors
        print(f"error: failed to parse {data_path}: {exc}", file=sys.stderr)
        return 2

    try:
        invoice = Invoice.from_mapping(raw, currency_override=args.currency)
    except (ValueError, TypeError) as exc:
        print(f"error: invalid invoice data: {exc}", file=sys.stderr)
        return 2

    try:
        if fmt == "pdf":
            render_pdf(invoice, output_path)
        else:
            html = render_html(invoice)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html, encoding="utf-8")
    except Exception as exc:  # rendering failure
        print(f"error: failed to render {fmt}: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        totals = invoice.compute_totals()
        print(
            f"Wrote {fmt.upper()} invoice {invoice.number} "
            f"({totals.grand_total.format()}) -> {output_path}"
        )
    return 0


def run() -> None:  # console_scripts entry point
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    run()
