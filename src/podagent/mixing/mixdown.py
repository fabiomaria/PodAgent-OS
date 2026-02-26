"""Multi-track mix-down to stereo WAV."""

from __future__ import annotations

from pathlib import Path

from podagent.utils.ffmpeg import run_ffmpeg
from podagent.utils.progress import log_step


def mixdown(
    track_paths: list[Path],
    output_path: Path,
    *,
    pan_enabled: bool = False,
    pan_spread: float = 0.1,
    sample_rate: int = 48000,
    bit_depth: int = 24,
) -> None:
    """Mix multiple mono tracks into a single stereo WAV.

    Args:
        pan_enabled: Apply stereo panning per track
        pan_spread: Panning amount (0.0=center, 0.5=hard L/R)
    """
    if not track_paths:
        raise ValueError("No tracks to mix")

    if len(track_paths) == 1:
        # Single track: convert to stereo
        log_step("Mixdown", "Single track → stereo")
        codec = f"pcm_s{bit_depth}le"
        run_ffmpeg([
            "-i", str(track_paths[0]),
            "-ac", "2",
            "-c:a", codec,
            "-ar", str(sample_rate),
            str(output_path),
        ])
        return

    log_step("Mixdown", f"Mixing {len(track_paths)} tracks → stereo")

    # Build FFmpeg filter complex
    inputs = []
    filter_parts = []

    for i, path in enumerate(track_paths):
        inputs.extend(["-i", str(path)])

        if pan_enabled:
            # Alternate panning: first track left-ish, second right-ish
            pan = -pan_spread if i % 2 == 0 else pan_spread
            filter_parts.append(f"[{i}:a]stereotools=mpan={pan}[t{i}]")
        else:
            # Center pan (duplicate mono to stereo)
            filter_parts.append(f"[{i}:a]aformat=channel_layouts=stereo[t{i}]")

    # Mix all tracks
    mix_inputs = "".join(f"[t{i}]" for i in range(len(track_paths)))
    filter_parts.append(
        f"{mix_inputs}amix=inputs={len(track_paths)}:duration=longest:normalize=0"
    )

    filter_complex = ";".join(filter_parts)
    codec = f"pcm_s{bit_depth}le"

    run_ffmpeg(
        inputs + [
            "-filter_complex", filter_complex,
            "-c:a", codec,
            "-ar", str(sample_rate),
            str(output_path),
        ]
    )

    log_step("Mixdown", f"Output: {output_path.name}")
