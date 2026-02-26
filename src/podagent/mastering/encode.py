"""MP3 encoding via FFmpeg/LAME."""

from __future__ import annotations

from pathlib import Path

from podagent.utils.ffmpeg import run_ffmpeg
from podagent.utils.progress import log_step


def encode_mp3(
    input_path: Path,
    output_path: Path,
    *,
    bitrate: int = 192,
    sample_rate: int = 44100,
    mono: bool = False,
) -> None:
    """Encode WAV to MP3 using libmp3lame."""
    log_step("Encode", f"MP3 {bitrate}kbps CBR, {sample_rate}Hz")

    channels_args = ["-ac", "1"] if mono else []

    run_ffmpeg([
        "-i", str(input_path),
        "-c:a", "libmp3lame",
        "-b:a", f"{bitrate}k",
        "-ar", str(sample_rate),
        *channels_args,
        "-id3v2_version", "4",
        "-write_xing", "1",
        str(output_path),
    ])

    size_mb = output_path.stat().st_size / 1_000_000
    log_step("Encode", f"MP3: {size_mb:.1f} MB")
