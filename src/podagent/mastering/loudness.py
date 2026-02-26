"""Two-pass loudness normalization via FFmpeg loudnorm."""

from __future__ import annotations

from pathlib import Path

from podagent.utils.ffmpeg import measure_loudness, run_ffmpeg
from podagent.utils.progress import log_step


def normalize_loudness(
    input_path: Path,
    output_path: Path,
    *,
    target_i: float = -16.0,
    target_tp: float = -1.0,
    target_lra: float = 11.0,
) -> dict:
    """Two-pass linear loudness normalization.

    Pass 1: Measure source loudness
    Pass 2: Apply linear gain with measured parameters

    Returns the measurements dict from Pass 1.
    """
    # Pass 1: Measure
    log_step("Loudness", "Pass 1: Measuring source loudness...")
    measurements = measure_loudness(input_path)

    input_i = measurements.get("input_i", "?")
    input_tp = measurements.get("input_tp", "?")
    input_lra = measurements.get("input_lra", "?")
    log_step(
        "Loudness",
        f"Source: {input_i} LUFS, TP: {input_tp} dBTP, LRA: {input_lra} LU",
    )

    # Pass 2: Normalize with linear mode
    log_step("Loudness", f"Pass 2: Normalizing to {target_i} LUFS (linear mode)...")

    loudnorm_filter = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}"
        f":measured_I={measurements['input_i']}"
        f":measured_TP={measurements['input_tp']}"
        f":measured_LRA={measurements['input_lra']}"
        f":measured_thresh={measurements['input_thresh']}"
        f":offset={measurements['target_offset']}"
        f":linear=true"
    )

    run_ffmpeg([
        "-i", str(input_path),
        "-af", loudnorm_filter,
        "-c:a", "pcm_s24le",
        "-ar", "48000",
        str(output_path),
    ])

    return measurements
