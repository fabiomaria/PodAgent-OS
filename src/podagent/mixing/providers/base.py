"""Base protocol for noise reduction providers."""

from __future__ import annotations

from typing import Protocol


class NoiseReductionProvider(Protocol):
    """Protocol for noise reduction providers."""

    name: str

    def process(self, input_path: str, output_path: str, **kwargs) -> None: ...
