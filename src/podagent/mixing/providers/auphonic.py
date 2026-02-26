"""Auphonic API noise reduction provider (stub)."""

from __future__ import annotations

from podagent.utils.progress import log_warning


class AuphonicNoiseReduction:
    """Noise reduction via Auphonic API (premium)."""

    name = "auphonic"

    def process(
        self,
        input_path: str,
        output_path: str,
        *,
        api_key: str | None = None,
    ) -> None:
        # Stub — would implement:
        # 1. POST /api/simple/productions.json
        # 2. Upload audio file
        # 3. Start production
        # 4. Poll for completion
        # 5. Download result
        raise NotImplementedError(
            "Auphonic provider not yet implemented. "
            "Use noise_reduction_provider='ffmpeg' in config."
        )
