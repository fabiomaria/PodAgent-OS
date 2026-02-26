"""Step 1: Audio validation — FFprobe validation, resampling."""

from __future__ import annotations

from pathlib import Path

from podagent.models.manifest import Manifest, SourceTrack
from podagent.utils.ffmpeg import resample
from podagent.utils.ffprobe import AudioInfo, probe_audio
from podagent.utils.progress import log, log_step, log_warning


MIN_DURATION = 10.0  # seconds
MAX_DURATION = 18000.0  # 5 hours


def validate_tracks(
    project_root: Path, manifest: Manifest
) -> list[AudioInfo]:
    """Validate all source tracks and return their metadata.

    Steps:
    1. Verify each file exists
    2. Probe with FFprobe for duration, sample_rate, channels, codec, bit_depth
    3. Validate constraints (min/max duration, sample rate, channels)
    4. If stereo, warn (will use left channel)
    5. If sample rates differ, resample all to highest rate
    6. Update manifest with source track metadata
    """
    track_infos: list[AudioInfo] = []

    for participant in manifest.project.participants:
        track_path = project_root / participant.track
        if not track_path.exists():
            raise FileNotFoundError(
                f"Track not found: {track_path} (for {participant.name})"
            )

        info = probe_audio(track_path)
        log_step(
            "Validate",
            f"{track_path.name} — "
            f"{info.duration_seconds:.0f}s, "
            f"{info.sample_rate}Hz, "
            f"{'stereo' if info.channels > 1 else 'mono'}, "
            f"{info.bit_depth or '?'}-bit",
        )

        # Duration checks
        if info.duration_seconds < MIN_DURATION:
            raise ValueError(
                f"Track too short ({info.duration_seconds:.1f}s): {track_path.name}. "
                f"Minimum is {MIN_DURATION}s."
            )
        if info.duration_seconds > MAX_DURATION:
            raise ValueError(
                f"Track too long ({info.duration_seconds:.0f}s): {track_path.name}. "
                f"Maximum is {MAX_DURATION:.0f}s."
            )

        # Channel warning
        if info.channels > 1:
            log_warning(
                f"{track_path.name} is stereo — will extract first channel only"
            )

        track_infos.append(info)

    # Check if resampling is needed
    sample_rates = set(i.sample_rate for i in track_infos)
    if len(sample_rates) > 1:
        target_rate = max(sample_rates)
        log(f"Sample rates differ, resampling all to {target_rate}Hz")
        track_infos = _resample_tracks(project_root, track_infos, target_rate)
    else:
        log(f"Sample rates match ({track_infos[0].sample_rate}Hz)")

    # Update manifest source_tracks
    manifest.files.source_tracks = [
        SourceTrack(
            path=info.path if not Path(info.path).is_absolute()
            else str(Path(info.path).relative_to(project_root)),
            duration_seconds=info.duration_seconds,
            sample_rate=info.sample_rate,
            channels=info.channels,
            format=info.format_short,
            bit_depth=info.bit_depth,
        )
        for info in track_infos
    ]

    return track_infos


def _resample_tracks(
    project_root: Path,
    track_infos: list[AudioInfo],
    target_rate: int,
) -> list[AudioInfo]:
    """Resample tracks that don't match the target sample rate."""
    resampled: list[AudioInfo] = []
    for info in track_infos:
        if info.sample_rate != target_rate:
            src = Path(info.path)
            dst = src.parent / f"{src.stem}_resampled{src.suffix}"
            log(f"Resampling {src.name}: {info.sample_rate}Hz → {target_rate}Hz")
            resample(src, dst, sample_rate=target_rate, channels=1)
            new_info = probe_audio(dst)
            resampled.append(new_info)
        else:
            resampled.append(info)
    return resampled
