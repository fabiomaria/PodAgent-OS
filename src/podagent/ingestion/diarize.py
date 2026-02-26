"""Step 3: Speaker diarization — multi-track VAD or pyannote fallback."""

from __future__ import annotations

from pathlib import Path

from podagent.models.manifest import Manifest
from podagent.utils.progress import log_step, log_warning


def get_diarization_strategy(manifest: Manifest) -> str:
    """Determine diarization strategy based on track count and config."""
    config = manifest.config.ingestion
    if config.diarization_strategy != "auto":
        return config.diarization_strategy

    num_tracks = len(manifest.project.participants)
    if num_tracks > 1:
        return "multi-track"
    return "single-track"


def diarize_multi_track(
    track_paths: list[Path],
    speakers: list[str],
) -> dict[str, list[tuple[float, float]]]:
    """Multi-track diarization: each track = one speaker.

    Returns dict mapping speaker name to list of (start, end) speech regions.
    Uses energy-based VAD to detect active speech per track.
    """
    log_step("Diarize", "Multi-track mode: speaker = track owner")

    speaker_regions: dict[str, list[tuple[float, float]]] = {}

    for track_path, speaker in zip(track_paths, speakers):
        regions = _detect_speech_regions(track_path)
        speaker_regions[speaker] = regions
        log_step("Diarize", f"  {speaker}: {len(regions)} speech regions")

    return speaker_regions


def _detect_speech_regions(
    track_path: Path,
    *,
    frame_duration_ms: int = 30,
    energy_threshold: float = 0.01,
    min_speech_ms: int = 250,
    min_silence_ms: int = 300,
) -> list[tuple[float, float]]:
    """Simple energy-based VAD for multi-track mode.

    For multi-track podcasts, we don't need pyannote — a simple energy
    threshold detects when the speaker on this track is active.
    """
    try:
        import numpy as np
        import soundfile as sf
    except ImportError:
        raise ImportError(
            "numpy and soundfile are required for diarization. "
            "Install with: pip install podagent-os[ingestion]"
        )

    audio, sr = sf.read(str(track_path), dtype="float32")

    # Use first channel if stereo
    if audio.ndim > 1:
        audio = audio[:, 0]

    frame_size = int(sr * frame_duration_ms / 1000)
    num_frames = len(audio) // frame_size

    # Compute RMS energy per frame
    is_speech = []
    for i in range(num_frames):
        frame = audio[i * frame_size : (i + 1) * frame_size]
        rms = float(np.sqrt(np.mean(frame**2)))
        is_speech.append(rms > energy_threshold)

    # Merge consecutive speech frames into regions
    regions: list[tuple[float, float]] = []
    in_speech = False
    speech_start = 0.0

    for i, speech in enumerate(is_speech):
        time_s = i * frame_duration_ms / 1000.0
        if speech and not in_speech:
            speech_start = time_s
            in_speech = True
        elif not speech and in_speech:
            duration_ms = (time_s - speech_start) * 1000
            if duration_ms >= min_speech_ms:
                regions.append((speech_start, time_s))
            in_speech = False

    # Close final region
    if in_speech:
        final_time = num_frames * frame_duration_ms / 1000.0
        regions.append((speech_start, final_time))

    # Merge regions separated by short silences
    merged: list[tuple[float, float]] = []
    for start, end in regions:
        if merged and (start - merged[-1][1]) * 1000 < min_silence_ms:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))

    return merged


def diarize_single_track(
    track_path: Path,
    num_speakers: int | None = None,
) -> dict[str, list[tuple[float, float]]]:
    """Single-track diarization using pyannote (fallback).

    Returns dict mapping speaker label to list of (start, end) regions.
    """
    try:
        from pyannote.audio import Pipeline
    except ImportError:
        log_warning(
            "pyannote.audio not available — skipping diarization. "
            "Speakers will be labeled 'Speaker_1'. "
            "Install with: pip install pyannote-audio"
        )
        return {"Speaker_1": []}

    import os

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        log_warning(
            "HF_TOKEN not set — pyannote requires a HuggingFace token. "
            "Set HF_TOKEN environment variable. Skipping diarization."
        )
        return {"Speaker_1": []}

    log_step("Diarize", "Single-track mode: running pyannote speaker-diarization-3.1")

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=hf_token,
    )

    kwargs = {}
    if num_speakers:
        kwargs["num_speakers"] = num_speakers

    diarization = pipeline(str(track_path), **kwargs)

    speaker_regions: dict[str, list[tuple[float, float]]] = {}
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        if speaker not in speaker_regions:
            speaker_regions[speaker] = []
        speaker_regions[speaker].append((turn.start, turn.end))

    for speaker, regions in speaker_regions.items():
        log_step("Diarize", f"  {speaker}: {len(regions)} speech regions")

    return speaker_regions
