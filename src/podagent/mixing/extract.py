"""Extract audio regions from source tracks via FFmpeg."""

from __future__ import annotations

from pathlib import Path

from podagent.mixing.timeline import AudioRegion
from podagent.utils.ffmpeg import extract_region
from podagent.utils.progress import log_step


def extract_regions(
    regions: list[AudioRegion],
    project_root: Path,
    tmp_dir: Path,
    *,
    sample_rate: int = 48000,
    bit_depth: int = 24,
) -> dict[str, Path]:
    """Extract audio regions from source tracks.

    Returns a mapping of edit_id → extracted file path.
    """
    tmp_dir.mkdir(parents=True, exist_ok=True)
    extracted: dict[str, Path] = {}

    log_step("Extract", f"Extracting {len(regions)} audio regions...")

    for i, region in enumerate(regions):
        if not region.track_path:
            continue

        track_path = project_root / region.track_path
        if not track_path.exists():
            raise FileNotFoundError(f"Source track not found: {track_path}")

        output_path = tmp_dir / f"region-{i:04d}.wav"
        duration = region.duration

        # Apply alignment offset
        adjusted_start = region.source_start + (region.offset_ms / 1000.0)
        adjusted_start = max(adjusted_start, 0.0)

        extract_region(
            track_path,
            output_path,
            start=adjusted_start,
            duration=duration,
            sample_rate=sample_rate,
            channels=1,
            bit_depth=bit_depth,
        )

        extracted[region.edit_id] = output_path

    log_step("Extract", f"Extracted {len(extracted)} regions to {tmp_dir}")
    return extracted
