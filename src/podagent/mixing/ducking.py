"""Auto-ducking automation for multi-track mixing."""

from __future__ import annotations

from dataclasses import dataclass

from podagent.mixing.timeline import AudioRegion
from podagent.utils.progress import log_step


@dataclass
class DuckingRegion:
    """A region where a track should be ducked."""

    track_path: str
    start: float
    end: float
    gain_db: float
    fade_in_ms: int
    fade_out_ms: int


def generate_ducking_automation(
    regions: list[AudioRegion],
    primary_speaker: str | None = None,
    *,
    ducking_db: float = -6.0,
    fade_in_ms: int = 50,
    fade_out_ms: int = 150,
) -> list[DuckingRegion]:
    """Generate volume automation for auto-ducking.

    When the primary speaker is talking, reduce volume of other tracks.
    If primary_speaker is None, the first speaker (host) is primary.
    """
    if not regions:
        return []

    # Determine primary speaker
    if primary_speaker is None:
        primary_speaker = regions[0].speaker

    # Find all primary speaker regions
    primary_regions = [r for r in regions if r.speaker == primary_speaker]
    other_regions = [r for r in regions if r.speaker != primary_speaker]

    ducking: list[DuckingRegion] = []

    for primary in primary_regions:
        for other in other_regions:
            # Check for overlap in record time
            overlap_start = max(primary.record_start, other.record_start)
            overlap_end = min(primary.record_end, other.record_end)

            if overlap_start < overlap_end:
                ducking.append(DuckingRegion(
                    track_path=other.track_path,
                    start=overlap_start,
                    end=overlap_end,
                    gain_db=ducking_db,
                    fade_in_ms=fade_in_ms,
                    fade_out_ms=fade_out_ms,
                ))

    log_step("Ducking", f"Generated {len(ducking)} ducking regions")
    return ducking


def build_volume_filter(
    ducking_regions: list[DuckingRegion],
    track_path: str,
) -> str | None:
    """Build an FFmpeg volume filter string for ducking a specific track.

    Returns None if no ducking needed for this track.
    """
    track_regions = [d for d in ducking_regions if d.track_path == track_path]
    if not track_regions:
        return None

    # Build volume expression using between() for each ducked region
    conditions = []
    for d in track_regions:
        db = d.gain_db
        conditions.append(f"between(t,{d.start:.3f},{d.end:.3f})")

    # Combine: if any ducking condition is true, apply ducking gain
    condition_str = "+".join(conditions)
    return f"volume='if({condition_str},{track_regions[0].gain_db}dB,0dB)':eval=frame"
