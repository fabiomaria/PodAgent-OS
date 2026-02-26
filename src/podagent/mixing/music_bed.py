"""Intro/outro music bed insertion."""

from __future__ import annotations

from pathlib import Path

from podagent.utils.ffmpeg import run_ffmpeg
from podagent.utils.progress import log_step


def mix_intro_music(
    speech_path: Path,
    music_path: Path,
    output_path: Path,
    *,
    music_volume_db: float = -12.0,
    duck_under_speech: bool = True,
) -> None:
    """Mix intro music under/before speech.

    If duck_under_speech, music fades down when speech starts.
    """
    if not music_path.exists():
        raise FileNotFoundError(f"Intro music not found: {music_path}")

    log_step("Music", f"Mixing intro music ({music_path.name})")

    if duck_under_speech:
        filter_complex = (
            f"[1:a]volume={music_volume_db}dB[music];"
            f"[music][0:a]sidechaincompress="
            f"threshold=-30dB:ratio=6:attack=50:release=500[ducked];"
            f"[0:a][ducked]amix=inputs=2:duration=first:normalize=0"
        )
    else:
        filter_complex = (
            f"[1:a]volume={music_volume_db}dB[music];"
            f"[0:a][music]amix=inputs=2:duration=first:normalize=0"
        )

    run_ffmpeg([
        "-i", str(speech_path),
        "-i", str(music_path),
        "-filter_complex", filter_complex,
        "-c:a", "pcm_s24le",
        str(output_path),
    ])


def mix_outro_music(
    speech_path: Path,
    music_path: Path,
    output_path: Path,
    *,
    music_volume_db: float = -12.0,
) -> None:
    """Append outro music after speech with a crossfade."""
    if not music_path.exists():
        raise FileNotFoundError(f"Outro music not found: {music_path}")

    log_step("Music", f"Appending outro music ({music_path.name})")

    # Crossfade between speech end and music start
    run_ffmpeg([
        "-i", str(speech_path),
        "-i", str(music_path),
        "-filter_complex",
        f"[1:a]volume={music_volume_db}dB[music];"
        f"[0:a][music]concat=n=2:v=0:a=1",
        "-c:a", "pcm_s24le",
        str(output_path),
    ])
