"""FFmpeg command builder and runner."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console

console = Console(stderr=True)


class FFmpegError(Exception):
    """Raised when an FFmpeg command fails."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str):
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"FFmpeg failed (rc={returncode}): {stderr[:500]}")


def run_ffmpeg(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """Run an FFmpeg command with standard options."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise FFmpegError(cmd, result.returncode, result.stderr)
    return result


def resample(
    input_path: Path | str,
    output_path: Path | str,
    sample_rate: int = 48000,
    channels: int = 1,
) -> None:
    """Resample an audio file to the target sample rate and channel count."""
    run_ffmpeg([
        "-i", str(input_path),
        "-ar", str(sample_rate),
        "-ac", str(channels),
        str(output_path),
    ])


def extract_region(
    input_path: Path | str,
    output_path: Path | str,
    start: float,
    duration: float,
    *,
    sample_rate: int = 48000,
    channels: int = 1,
    bit_depth: int = 24,
) -> None:
    """Extract a time region from an audio file."""
    codec = f"pcm_s{bit_depth}le"
    run_ffmpeg([
        "-ss", str(start),
        "-i", str(input_path),
        "-t", str(duration),
        "-c:a", codec,
        "-ar", str(sample_rate),
        "-ac", str(channels),
        str(output_path),
    ])


def apply_filter(
    input_path: Path | str,
    output_path: Path | str,
    audio_filter: str,
    *,
    codec: str = "pcm_s24le",
    sample_rate: int | None = None,
) -> None:
    """Apply an audio filter to a file."""
    args = [
        "-i", str(input_path),
        "-af", audio_filter,
        "-c:a", codec,
    ]
    if sample_rate:
        args.extend(["-ar", str(sample_rate)])
    args.append(str(output_path))
    run_ffmpeg(args)


def measure_loudness(input_path: Path | str) -> dict:
    """Measure loudness using the loudnorm filter (pass 1)."""
    import json
    import re

    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner",
            "-i", str(input_path),
            "-af", "loudnorm=I=-16:TP=-1:LRA=11:print_format=json",
            "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
    )

    json_match = re.search(r"\{[^}]+\}", result.stderr, re.DOTALL)
    if not json_match:
        raise RuntimeError(f"Failed to parse loudnorm output from: {input_path}")

    return json.loads(json_match.group())


def generate_waveform(
    input_path: Path | str,
    output_path: Path | str,
    width: int = 1920,
    height: int = 400,
    color: str = "0x4a9eff",
) -> None:
    """Generate a waveform image from an audio file."""
    run_ffmpeg([
        "-i", str(input_path),
        "-filter_complex", f"showwavespic=s={width}x{height}:colors={color}",
        "-frames:v", "1",
        str(output_path),
    ])
