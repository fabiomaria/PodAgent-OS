"""Crossfade between audio regions at edit points."""

from __future__ import annotations

import subprocess
from pathlib import Path

from podagent.utils.ffmpeg import FFmpegError, run_ffmpeg
from podagent.utils.progress import log_warning


def apply_crossfade(
    region_a: Path,
    region_b: Path,
    output: Path,
    *,
    duration_ms: int = 50,
    curve: str = "tri",
) -> None:
    """Apply a crossfade between two consecutive audio regions.

    Args:
        duration_ms: Crossfade duration in milliseconds
        curve: Crossfade curve type (tri, exp, log)
    """
    duration_s = duration_ms / 1000.0

    try:
        run_ffmpeg([
            "-i", str(region_a),
            "-i", str(region_b),
            "-filter_complex",
            f"acrossfade=d={duration_s}:c1={curve}:c2={curve}",
            "-c:a", "pcm_s24le",
            str(output),
        ])
    except FFmpegError:
        # Fallback: concatenate without crossfade if regions too short
        log_warning(
            f"Crossfade failed (regions may be too short). Using hard cut."
        )
        concatenate(region_a, region_b, output)


def concatenate(file_a: Path, file_b: Path, output: Path) -> None:
    """Concatenate two audio files without crossfade."""
    # Create concat list file
    list_path = output.parent / f"{output.stem}_concat.txt"
    list_path.write_text(f"file '{file_a}'\nfile '{file_b}'\n")

    run_ffmpeg([
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
        "-c:a", "pcm_s24le",
        str(output),
    ])

    list_path.unlink(missing_ok=True)


def concatenate_all(files: list[Path], output: Path) -> None:
    """Concatenate multiple audio files sequentially."""
    if not files:
        return
    if len(files) == 1:
        import shutil
        shutil.copy2(files[0], output)
        return

    list_path = output.parent / f"{output.stem}_concat.txt"
    list_path.write_text(
        "\n".join(f"file '{f}'" for f in files) + "\n"
    )

    run_ffmpeg([
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
        "-c:a", "pcm_s24le",
        str(output),
    ])

    list_path.unlink(missing_ok=True)
