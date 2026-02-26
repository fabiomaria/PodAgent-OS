"""FFprobe wrapper for audio file metadata extraction."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AudioInfo:
    """Audio file metadata extracted via FFprobe."""

    path: str
    duration_seconds: float
    sample_rate: int
    channels: int
    codec: str
    bit_depth: int | None
    format_name: str

    @property
    def format_short(self) -> str:
        if "wav" in self.format_name:
            return "wav"
        if "flac" in self.format_name:
            return "flac"
        if "mp3" in self.format_name or self.codec == "mp3":
            return "mp3"
        return self.format_name


def probe_audio(path: Path | str) -> AudioInfo:
    """Probe an audio file with FFprobe and return metadata."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    result = subprocess.run(
        [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    data = json.loads(result.stdout)

    audio_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "audio":
            audio_stream = stream
            break

    if audio_stream is None:
        raise ValueError(f"No audio stream found in: {path}")

    fmt = data.get("format", {})

    # Extract bit depth from bits_per_raw_sample or bits_per_sample
    bit_depth = None
    for key in ("bits_per_raw_sample", "bits_per_sample"):
        val = audio_stream.get(key)
        if val and str(val).isdigit() and int(val) > 0:
            bit_depth = int(val)
            break

    return AudioInfo(
        path=str(path),
        duration_seconds=float(fmt.get("duration", audio_stream.get("duration", 0))),
        sample_rate=int(audio_stream.get("sample_rate", 0)),
        channels=int(audio_stream.get("channels", 0)),
        codec=audio_stream.get("codec_name", ""),
        bit_depth=bit_depth,
        format_name=fmt.get("format_name", ""),
    )
