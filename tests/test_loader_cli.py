"""Tests for the data loader (format inference) and the argparse CLI."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from invoice_generator import cli
from invoice_generator.loader import (
    UnsupportedFormatError,
    detect_format,
    load_file,
    load_mapping,
)

pypdf = pytest.importorskip("pypdf")

JSON_TEXT = """
{
  "number": "L-JSON-1",
  "currency": "USD",
  "seller": {"name": "S Co"},
  "client": {"name": "C Co"},
  "items": [{"description": "X", "quantity": 2, "unit_price": "5.00"}]
}
"""

YAML_TEXT = """
number: L-YAML-1
currency: USD
seller: {name: S Co}
client: {name: C Co}
items:
  - {description: X, quantity: 2, unit_price: "5.00"}
"""

TOML_TEXT = """
number = "L-TOML-1"
currency = "USD"
[seller]
name = "S Co"
[client]
name = "C Co"
[[items]]
description = "X"
quantity = 2
unit_price = "5.00"
"""


def test_detect_format():
    assert detect_format(Path("a.json")) == "json"
    assert detect_format(Path("a.yaml")) == "yaml"
    assert detect_format(Path("a.yml")) == "yaml"
    assert detect_format(Path("a.toml")) == "toml"
    with pytest.raises(UnsupportedFormatError):
        detect_format(Path("a.txt"))


def test_load_each_format_equivalent():
    j = load_mapping(JSON_TEXT, "json")
    y = load_mapping(YAML_TEXT, "yaml")
    t = load_mapping(TOML_TEXT, "toml")
    for m in (j, y, t):
        assert m["seller"]["name"] == "S Co"
        assert m["items"][0]["quantity"] == 2


def test_load_file_by_extension(tmp_path):
    p = tmp_path / "data.yaml"
    p.write_text(YAML_TEXT, encoding="utf-8")
    m = load_file(p)
    assert m["number"] == "L-YAML-1"


def test_load_file_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_file(tmp_path / "nope.json")


# ---- CLI ----


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_cli_generates_pdf(tmp_path):
    data = _write(tmp_path, "inv.json", JSON_TEXT)
    out = tmp_path / "inv.pdf"
    rc = cli.main([str(data), "-o", str(out)])
    assert rc == 0
    assert out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"


def test_cli_default_output_is_pdf_next_to_data(tmp_path):
    data = _write(tmp_path, "inv.json", JSON_TEXT)
    rc = cli.main([str(data)])
    assert rc == 0
    assert (tmp_path / "inv.pdf").exists()


def test_cli_html_by_extension(tmp_path):
    data = _write(tmp_path, "inv.toml", TOML_TEXT)
    out = tmp_path / "inv.html"
    rc = cli.main([str(data), "-o", str(out)])
    assert rc == 0
    html = out.read_text(encoding="utf-8")
    assert "L-TOML-1" in html
    assert "$10.00" in html  # 2 x 5.00


def test_cli_format_flag_overrides(tmp_path):
    data = _write(tmp_path, "inv.yaml", YAML_TEXT)
    out = tmp_path / "out.bin"  # extension would be ambiguous
    rc = cli.main([str(data), "-o", str(out), "--format", "html"])
    assert rc == 0
    assert "L-YAML-1" in out.read_text(encoding="utf-8")


def test_cli_currency_override(tmp_path, capsys):
    data = _write(tmp_path, "inv.json", JSON_TEXT)
    out = tmp_path / "inv.html"
    rc = cli.main([str(data), "-o", str(out), "--currency", "EUR"])
    assert rc == 0
    assert "€10.00" in out.read_text(encoding="utf-8")


def test_cli_missing_file_returns_2(tmp_path, capsys):
    rc = cli.main([str(tmp_path / "ghost.json")])
    assert rc == 2
    err = capsys.readouterr().err
    assert "error" in err.lower()


def test_cli_bad_data_returns_2(tmp_path):
    data = _write(tmp_path, "bad.json", '{"seller": {"name": "S"}}')
    rc = cli.main([str(data), "-o", str(tmp_path / "x.pdf")])
    assert rc == 2


def test_cli_success_message(tmp_path, capsys):
    data = _write(tmp_path, "inv.json", JSON_TEXT)
    out = tmp_path / "inv.pdf"
    cli.main([str(data), "-o", str(out)])
    captured = capsys.readouterr().out
    assert "L-JSON-1" in captured
    assert "$10.00" in captured
