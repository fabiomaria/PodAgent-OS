"""Configuration models for each pipeline module."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IngestionConfig(BaseModel):
    """Configuration for the ingestion module."""

    transcription_model: str = "large-v3-turbo"
    transcription_device: str = "cpu"
    transcription_language: str | None = None
    vad_enabled: bool = True
    vad_min_silence_ms: int = Field(default=500, ge=100, le=5000)
    diarization_strategy: str = "auto"  # auto | multi-track | single-track
    diarization_num_speakers: int | None = None
    alignment_segment_seconds: int = Field(default=60, ge=10, le=120)
    llm_model: str = "claude-sonnet-4-6"
    llm_chunk_minutes: int = Field(default=15, ge=5, le=30)
    custom_vocabulary_path: str | None = None
    voice_profiles_path: str | None = None


class EditingConfig(BaseModel):
    """Configuration for the editing module."""

    filler_sensitivity: float = Field(default=0.7, ge=0.0, le=1.0)
    tangent_sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    min_silence_duration_ms: int = Field(default=800, ge=200, le=5000)
    silence_keep_ms: int = Field(default=300, ge=100, le=1000)
    speaker_turn_pause_ms: int = Field(default=500, ge=200, le=1500)
    tangent_auto_cut_threshold: float = Field(default=0.85, ge=0.5, le=1.0)
    max_tangent_keep_seconds: int = Field(default=30, ge=10, le=120)
    detect_false_starts: bool = True
    generate_chapters: bool = True
    generate_show_notes: bool = True
    llm_model: str = "claude-sonnet-4-6"
    edl_frame_rate: int = 30
    crossfade_duration_ms: int = Field(default=50, ge=0, le=500)


class MixingConfig(BaseModel):
    """Configuration for the mixing module."""

    noise_reduction_provider: str = "ffmpeg"  # ffmpeg | auphonic | dolby | none
    noise_floor_db: int = Field(default=-25, ge=-40, le=-10)
    compression_enabled: bool = True
    compression_threshold_db: int = Field(default=-20, ge=-40, le=0)
    compression_ratio: float = Field(default=3.0, ge=1.5, le=10.0)
    compression_attack_ms: int = Field(default=10, ge=1, le=100)
    compression_release_ms: int = Field(default=200, ge=50, le=1000)
    de_essing_enabled: bool = False
    crossfade_duration_ms: int = Field(default=50, ge=0, le=500)
    crossfade_curve: str = "tri"  # tri | exp | log
    ducking_enabled: bool = True
    ducking_threshold_db: float = Field(default=-6.0, ge=-20.0, le=0.0)
    ducking_fade_in_ms: int = Field(default=50, ge=10, le=500)
    ducking_fade_out_ms: int = Field(default=150, ge=50, le=1000)
    primary_speaker: str | None = None
    output_sample_rate: int = 48000
    output_bit_depth: int = 24
    pan_enabled: bool = False
    pan_spread: float = Field(default=0.1, ge=0.0, le=0.5)
    music_intro_path: str | None = None
    music_outro_path: str | None = None
    music_volume_db: float = Field(default=-12.0, ge=-30.0, le=0.0)


class MasteringConfig(BaseModel):
    """Configuration for the mastering module."""

    target_lufs: float = Field(default=-16.0, ge=-24.0, le=-8.0)
    true_peak_limit_dbtp: float = Field(default=-1.0, ge=-3.0, le=0.0)
    loudnorm_lra: float = Field(default=11.0, ge=5.0, le=20.0)
    mp3_bitrate_kbps: int = 192
    mp3_sample_rate: int = 44100
    mp3_mono: bool = False
    output_formats: list[str] = Field(default_factory=lambda: ["mp3", "wav"])
    cover_art_path: str | None = None
    cover_art_max_px: int = Field(default=3000, ge=1400, le=3000)
    embed_chapters: bool = True
    generate_html_notes: bool = True
    id3_genre: str = "Podcast"
    id3_publisher: str | None = None
    id3_url: str | None = None
    verify_output: bool = True
