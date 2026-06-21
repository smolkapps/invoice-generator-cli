"""Load structured invoice data from JSON / YAML / TOML by file extension."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

# TOML: stdlib tomllib on 3.11+, fall back to the tomli backport otherwise.
try:  # pragma: no cover - import path depends on interpreter version
    import tomllib as _toml  # type: ignore[attr-defined]

    _TOML_LOADS = _toml.loads
except ModuleNotFoundError:  # pragma: no cover - py<3.11
    try:
        import tomli as _toml  # type: ignore[no-redef]

        _TOML_LOADS = _toml.loads
    except ModuleNotFoundError:  # pragma: no cover
        _TOML_LOADS = None


_JSON_EXT = {".json"}
_YAML_EXT = {".yaml", ".yml"}
_TOML_EXT = {".toml"}


class UnsupportedFormatError(ValueError):
    """Raised when a file extension does not map to a known format."""


def detect_format(path: Path) -> str:
    """Return one of ``"json"``, ``"yaml"``, ``"toml"`` from the extension."""
    ext = path.suffix.lower()
    if ext in _JSON_EXT:
        return "json"
    if ext in _YAML_EXT:
        return "yaml"
    if ext in _TOML_EXT:
        return "toml"
    raise UnsupportedFormatError(
        f"cannot infer format from extension {ext!r}; "
        f"use a .json, .yaml/.yml, or .toml file"
    )


def load_mapping(text: str, fmt: str) -> Mapping[str, Any]:
    """Parse ``text`` according to ``fmt`` and return a mapping."""
    if fmt == "json":
        data = json.loads(text)
    elif fmt == "yaml":
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError(
                "PyYAML is required to read YAML files (pip install pyyaml)"
            ) from exc
        data = yaml.safe_load(text)
    elif fmt == "toml":
        if _TOML_LOADS is None:  # pragma: no cover
            raise RuntimeError(
                "TOML support requires Python 3.11+ or the 'tomli' package"
            )
        data = _TOML_LOADS(text)
    else:  # pragma: no cover - guarded by detect_format
        raise UnsupportedFormatError(f"unknown format {fmt!r}")

    if not isinstance(data, Mapping):
        raise ValueError("top-level data must be an object/mapping")
    return data


def load_file(path: str | Path) -> Mapping[str, Any]:
    """Read and parse an invoice data file, inferring format from extension."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"no such file: {p}")
    fmt = detect_format(p)
    text = p.read_text(encoding="utf-8")
    return load_mapping(text, fmt)
