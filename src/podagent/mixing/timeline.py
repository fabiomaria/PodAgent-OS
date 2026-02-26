"""Build edit timeline from JSON sidecar."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from podagent.models.alignment import AlignmentMap
from podagent.models.edl import EDLSidecar, Edit
from podagent.utils.progress import log_step


@dataclass
class AudioRegion:
    """A region of audio to include in the mix."""

    edit_id: str
    track_path: str
    source_start: float
    source_end: float
    record_start: float
    record_end: float
    speaker: str
    offset_ms: float  # alignment offset

    @property
    def duration(self) -> float:
        return self.source_end - self.source_start


def build_timeline(
    edl: EDLSidecar,
    alignment: AlignmentMap,
    track_map: dict[str, str],
) -> list[AudioRegion]:
    """Build an ordered list of audio regions from the EDL.

    Args:
        edl: The edit decision list
        alignment: Track alignment information
        track_map: Maps speaker names to track file paths
    """
    regions: list[AudioRegion] = []

    for edit in edl.keep_edits:
        speaker = edit.speaker or ""
        track_path = track_map.get(speaker, "")
        offset_ms = alignment.get_track_offset(track_path) if track_path else 0.0

        regions.append(AudioRegion(
            edit_id=edit.id,
            track_path=track_path,
            source_start=edit.source_start,
            source_end=edit.source_end,
            record_start=edit.record_start or 0.0,
            record_end=edit.record_end or 0.0,
            speaker=speaker,
            offset_ms=offset_ms,
        ))

    # Sort by record position (output timeline order)
    regions.sort(key=lambda r: r.record_start)

    log_step("Timeline", f"Built timeline: {len(regions)} regions")
    return regions
