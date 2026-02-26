"""File I/O utilities — atomic writes, YAML handling."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.default_flow_style = False


def write_atomic(path: Path | str, data: Any, *, as_yaml: bool = False) -> None:
    """Write data to a file atomically (write to temp, then rename)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=path.parent,
        suffix=path.suffix,
        delete=False,
    ) as tmp:
        if as_yaml:
            _yaml.dump(data, tmp)
        elif isinstance(data, str):
            tmp.write(data)
        else:
            json.dump(data, tmp, indent=2, default=str)
        tmp_path = Path(tmp.name)

    tmp_path.rename(path)


def read_yaml(path: Path | str) -> dict:
    """Read a YAML file and return as dict."""
    path = Path(path)
    with open(path) as f:
        return dict(_yaml.load(f) or {})


def write_yaml(path: Path | str, data: dict) -> None:
    """Write a dict to a YAML file atomically."""
    write_atomic(path, data, as_yaml=True)


def read_json(path: Path | str) -> dict:
    """Read a JSON file and return as dict."""
    with open(path) as f:
        return json.load(f)


def write_json(path: Path | str, data: Any) -> None:
    """Write data to a JSON file atomically."""
    write_atomic(path, data)


def file_checksum(path: Path | str) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
