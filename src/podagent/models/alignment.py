"""Alignment map model for multi-track synchronization."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AlignedTrack(BaseModel):
    """A single track's alignment information."""

    path: str
    offset_ms: float = 0.0
    duration_ms: float = 0.0
    sample_rate: int = 48000
    channels: int = 1
    is_reference: bool = False
    alignment_confidence: float | None = None
    alignment_method: str | None = None


class CommonTimeline(BaseModel):
    """The shared timeline all tracks are aligned to."""

    start_ms: float = 0.0
    end_ms: float = 0.0


class AlignmentMap(BaseModel):
    """Maps multi-track recordings to a common timeline."""

    version: str = "1.0"
    reference_track: str = ""
    tracks: list[AlignedTrack] = Field(default_factory=list)
    common_timeline: CommonTimeline = Field(default_factory=CommonTimeline)

    def get_track_offset(self, path: str) -> float:
        for track in self.tracks:
            if track.path == path:
                return track.offset_ms
        return 0.0
