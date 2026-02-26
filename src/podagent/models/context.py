"""Context document model — LLM-generated episode analysis."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Topic(BaseModel):
    """A topic discussed in the episode."""

    name: str
    start_segment: str | None = None
    end_segment: str | None = None
    start_time: float = 0.0
    end_time: float = 0.0
    description: str = ""


class ProperNoun(BaseModel):
    """A proper noun mentioned in the episode."""

    text: str
    category: str = ""  # organization | product | person | place
    occurrences: int = 0


class StructuralSegment(BaseModel):
    """A structural segment of the episode."""

    type: str  # intro | main_topic | tangent | aside | outro
    label: str | None = None
    start_time: float = 0.0
    end_time: float = 0.0
    confidence: float | None = None


class KeyQuote(BaseModel):
    """A notable quote from the episode."""

    speaker: str
    text: str
    time: float = 0.0
    segment: str | None = None


class ContextMetadata(BaseModel):
    """Metadata about LLM context extraction."""

    llm_model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    processing_time_seconds: float = 0.0


class ContextDocument(BaseModel):
    """Semantic analysis of the episode content."""

    version: str = "1.0"
    episode_summary: str = ""
    topics: list[Topic] = Field(default_factory=list)
    proper_nouns: list[ProperNoun] = Field(default_factory=list)
    structural_segments: list[StructuralSegment] = Field(default_factory=list)
    key_quotes: list[KeyQuote] = Field(default_factory=list)
    metadata: ContextMetadata = Field(default_factory=ContextMetadata)
