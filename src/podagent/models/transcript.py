"""Transcript data models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Word(BaseModel):
    """A single transcribed word with timing."""

    word: str
    start: float
    end: float
    confidence: float = 0.0


class Segment(BaseModel):
    """A transcript segment (contiguous speech by one speaker)."""

    id: str
    speaker: str
    start: float
    end: float
    text: str
    words: list[Word] = Field(default_factory=list)
    source_track: str | None = None

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def word_count(self) -> int:
        return len(self.words) if self.words else len(self.text.split())


class TranscriptMetadata(BaseModel):
    """Metadata about transcription processing."""

    transcription_model: str = ""
    diarization_model: str = ""
    processing_time_seconds: float = 0.0
    word_count: int = 0
    segment_count: int = 0


class Transcript(BaseModel):
    """Complete episode transcript."""

    version: str = "1.0"
    episode_id: str = ""
    duration_seconds: float = 0.0
    language: str = "en"
    segments: list[Segment] = Field(default_factory=list)
    metadata: TranscriptMetadata = Field(default_factory=TranscriptMetadata)
