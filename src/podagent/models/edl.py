"""EDL (Edit Decision List) sidecar model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Edit(BaseModel):
    """A single edit decision."""

    id: str
    type: str  # keep | cut
    source_track: str
    source_start: float
    source_end: float
    record_start: float | None = None
    record_end: float | None = None
    transition: str = "cut"  # cut | crossfade
    speaker: str | None = None
    description: str = ""
    reason: str | None = None  # filler | silence | tangent | false_start
    confidence: float | None = None
    rationale: str | None = None
    segments: list[str] = Field(default_factory=list)
    auto_applied: bool = False
    review_flag: str | None = None

    @property
    def duration(self) -> float:
        return self.source_end - self.source_start


class Transition(BaseModel):
    """A transition between two edits."""

    between: list[str]  # [edit_id_a, edit_id_b]
    type: str = "crossfade"
    duration_ms: int = 50


class EDLSidecar(BaseModel):
    """Rich internal representation of the edit decision list."""

    version: str = "1.0"
    episode_id: str = ""
    original_duration_seconds: float = 0.0
    edited_duration_seconds: float = 0.0
    time_removed_seconds: float = 0.0
    time_removed_percent: float = 0.0
    edl_frame_rate: int = 30
    edl_mode: str = "NON-DROP FRAME"
    edits: list[Edit] = Field(default_factory=list)
    transitions: list[Transition] = Field(default_factory=list)

    @property
    def keep_edits(self) -> list[Edit]:
        return [e for e in self.edits if e.type == "keep"]

    @property
    def cut_edits(self) -> list[Edit]:
        return [e for e in self.edits if e.type == "cut"]
