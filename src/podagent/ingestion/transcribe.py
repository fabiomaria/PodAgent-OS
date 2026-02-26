"""Step 2: Whisper transcription — faster-whisper CPU mode."""

from __future__ import annotations

import time
from pathlib import Path

from podagent.models.transcript import Segment, TranscriptMetadata, Word
from podagent.utils.progress import log_step, log_warning


def transcribe_tracks(
    track_paths: list[Path],
    speakers: list[str],
    *,
    model_size: str = "large-v3-turbo",
    device: str = "cpu",
    language: str | None = None,
    vad_enabled: bool = True,
    vad_min_silence_ms: int = 500,
) -> tuple[dict[str, list[Segment]], TranscriptMetadata]:
    """Transcribe multiple tracks using faster-whisper.

    Returns a dict mapping speaker name to their segments, plus metadata.
    The Whisper model is loaded once and reused across all tracks.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError(
            "faster-whisper is required for transcription. "
            "Install with: pip install podagent-os[ingestion]"
        )

    compute_type = "int8" if device == "cpu" else "float16"
    log_step("Transcribe", f"Loading model: {model_size} ({device}, {compute_type})")

    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    all_segments: dict[str, list[Segment]] = {}
    total_words = 0
    total_segments = 0
    start_time = time.time()

    for track_path, speaker in zip(track_paths, speakers):
        log_step("Transcribe", f"Transcribing {track_path.name} ({speaker})...")

        vad_params = None
        if vad_enabled:
            vad_params = dict(
                min_silence_duration_ms=vad_min_silence_ms,
                speech_pad_ms=200,
            )

        segments_gen, info = model.transcribe(
            str(track_path),
            beam_size=5,
            word_timestamps=True,
            vad_filter=vad_enabled,
            vad_parameters=vad_params,
            language=language,
        )

        track_segments: list[Segment] = []
        seg_count = 0

        for seg in segments_gen:
            words = []
            if seg.words:
                for w in seg.words:
                    words.append(Word(
                        word=w.word.strip(),
                        start=w.start,
                        end=w.end,
                        confidence=w.probability,
                    ))

            segment = Segment(
                id="",  # Will be assigned during merge
                speaker=speaker,
                start=seg.start,
                end=seg.end,
                text=seg.text.strip(),
                words=words,
                source_track=str(track_path.name),
            )
            track_segments.append(segment)
            seg_count += 1
            total_words += len(words)

        total_segments += seg_count
        all_segments[speaker] = track_segments

        log_step(
            "Transcribe",
            f"  {track_path.name}: {seg_count} segments, "
            f"{sum(len(s.words) for s in track_segments)} words",
        )

    elapsed = time.time() - start_time
    detected_language = "en"  # Default

    metadata = TranscriptMetadata(
        transcription_model=f"faster-whisper-{model_size}",
        processing_time_seconds=elapsed,
        word_count=total_words,
        segment_count=total_segments,
    )

    return all_segments, metadata
