"""Dolby.io API noise reduction provider (stub)."""

from __future__ import annotations


class DolbyNoiseReduction:
    """Noise reduction via Dolby.io Media API (premium)."""

    name = "dolby"

    def process(
        self,
        input_path: str,
        output_path: str,
        *,
        api_key: str | None = None,
    ) -> None:
        raise NotImplementedError(
            "Dolby.io provider not yet implemented. "
            "Use noise_reduction_provider='ffmpeg' in config."
        )
