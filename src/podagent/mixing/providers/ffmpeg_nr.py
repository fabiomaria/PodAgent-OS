"""FFmpeg afftdn noise reduction provider."""

from __future__ import annotations

from podagent.utils.ffmpeg import apply_filter


class FFmpegNoiseReduction:
    """Noise reduction via FFmpeg's afftdn (adaptive FFT denoiser)."""

    name = "ffmpeg"

    def process(
        self,
        input_path: str,
        output_path: str,
        *,
        noise_floor_db: int = -25,
    ) -> None:
        apply_filter(
            input_path,
            output_path,
            f"afftdn=nf={noise_floor_db}",
        )
