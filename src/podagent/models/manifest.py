"""Manifest model — single source of truth for episode state."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from podagent.models.config import (
    EditingConfig,
    IngestionConfig,
    MasteringConfig,
    MixingConfig,
)


class Participant(BaseModel):
    """A participant in the podcast episode."""

    name: str
    role: str  # host | guest | co-host
    track: str  # relative path to audio file


class Project(BaseModel):
    """Episode project metadata."""

    name: str
    episode_number: int
    title: str
    recording_date: str
    participants: list[Participant] = Field(default_factory=list)


class SourceTrack(BaseModel):
    """Metadata about a source audio track."""

    path: str
    duration_seconds: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    format: str | None = None
    bit_depth: int | None = None


class Files(BaseModel):
    """Paths to all artifact files."""

    source_tracks: list[SourceTrack] = Field(default_factory=list)
    transcript: str = "artifacts/ingestion/transcript.json"
    alignment_map: str = "artifacts/ingestion/alignment.json"
    context_document: str = "artifacts/ingestion/context.json"
    edl: str = "artifacts/editing/edit-list.edl"
    edl_sidecar: str = "artifacts/editing/edit-list.json"
    edit_rationale: str = "artifacts/editing/rationale.json"
    content_summary: str = "artifacts/editing/summary.md"
    mixed_audio: str = "artifacts/mixing/mixed.wav"
    mixing_log: str = "artifacts/mixing/mixing-log.json"
    waveform: str = "artifacts/mixing/waveform.png"
    mastered_mp3: str = "artifacts/mastering/episode.mp3"
    mastered_wav: str = "artifacts/mastering/episode.wav"
    show_notes_md: str = "artifacts/mastering/show-notes.md"
    show_notes_html: str = "artifacts/mastering/show-notes.html"
    metadata_json: str = "artifacts/mastering/metadata.json"


class StageError(BaseModel):
    """Error info for a failed stage."""

    type: str
    message: str
    step: str | None = None


class StageStatus(BaseModel):
    """Status of a single pipeline stage."""

    status: str = "pending"  # pending | in_progress | completed | failed
    started_at: datetime | None = None
    completed_at: datetime | None = None
    gate_approved: bool | None = None
    gate_approved_at: datetime | None = None
    gate_notes: str | None = None
    error: StageError | None = None
    last_completed_step: str | None = None
    artifact_checksums: dict[str, str] = Field(default_factory=dict)


class Pipeline(BaseModel):
    """Pipeline execution state."""

    current_stage: str = "ingestion"
    stages: dict[str, StageStatus] = Field(
        default_factory=lambda: {
            "ingestion": StageStatus(),
            "editing": StageStatus(),
            "mixing": StageStatus(),
            "mastering": StageStatus(),
        }
    )


class Config(BaseModel):
    """All module configurations."""

    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    editing: EditingConfig = Field(default_factory=EditingConfig)
    mixing: MixingConfig = Field(default_factory=MixingConfig)
    mastering: MasteringConfig = Field(default_factory=MasteringConfig)


class Manifest(BaseModel):
    """The project manifest — single source of truth for an episode."""

    version: str = "1.0"
    project: Project
    files: Files = Field(default_factory=Files)
    pipeline: Pipeline = Field(default_factory=Pipeline)
    config: Config = Field(default_factory=Config)

    def get_stage(self, name: str) -> StageStatus:
        return self.pipeline.stages[name]

    def project_root(self, manifest_path: Path) -> Path:
        return manifest_path.parent
