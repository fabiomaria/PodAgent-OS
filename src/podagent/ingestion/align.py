"""Step 4: Multi-track alignment via cross-correlation."""

from __future__ import annotations

from pathlib import Path

from podagent.models.alignment import AlignedTrack, AlignmentMap, CommonTimeline
from podagent.utils.ffprobe import probe_audio
from podagent.utils.progress import log_step, log_warning


ALIGNMENT_CONFIDENCE_THRESHOLD = 0.3


def align_tracks(
    project_root: Path,
    track_paths: list[Path],
    *,
    segment_seconds: int = 60,
    downsample_rate: int = 16000,
) -> AlignmentMap:
    """Align multiple tracks to a common timeline via cross-correlation.

    Strategy:
    1. Select first track (host) as reference
    2. Downsample to 16kHz for efficiency (36x fewer operations)
    3. Cross-correlate first segment_seconds of each track against reference
    4. Lag at correlation peak = time offset
    5. If confidence < threshold, try bandpass filtering then retry
    """
    if len(track_paths) < 2:
        return _single_track_alignment(project_root, track_paths[0])

    try:
        import numpy as np
        import soundfile as sf
    except ImportError:
        raise ImportError(
            "numpy and soundfile are required for alignment. "
            "Install with: pip install podagent-os[ingestion]"
        )

    reference_path = track_paths[0]
    reference_info = probe_audio(reference_path)

    log_step("Align", f"Reference track: {reference_path.name}")

    # Load reference audio (downsampled)
    ref_audio = _load_downsampled(reference_path, downsample_rate, segment_seconds)

    aligned_tracks = [
        AlignedTrack(
            path=str(reference_path.relative_to(project_root)),
            offset_ms=0.0,
            duration_ms=reference_info.duration_seconds * 1000,
            sample_rate=reference_info.sample_rate,
            channels=reference_info.channels,
            is_reference=True,
        )
    ]

    max_duration = reference_info.duration_seconds

    for track_path in track_paths[1:]:
        track_info = probe_audio(track_path)
        max_duration = max(max_duration, track_info.duration_seconds)

        target_audio = _load_downsampled(track_path, downsample_rate, segment_seconds)

        offset_ms, confidence = _cross_correlate(
            ref_audio, target_audio, downsample_rate
        )

        method = "cross-correlation"

        # Fallback: bandpass filter and retry if low confidence
        if confidence < ALIGNMENT_CONFIDENCE_THRESHOLD:
            log_warning(
                f"Low alignment confidence ({confidence:.3f}) for {track_path.name}. "
                "Retrying with bandpass filter..."
            )
            ref_filtered = _bandpass_filter(ref_audio, downsample_rate)
            target_filtered = _bandpass_filter(target_audio, downsample_rate)
            offset_ms_bp, confidence_bp = _cross_correlate(
                ref_filtered, target_filtered, downsample_rate
            )
            if confidence_bp > confidence:
                offset_ms = offset_ms_bp
                confidence = confidence_bp
                method = "cross-correlation-bandpass"

        if confidence < ALIGNMENT_CONFIDENCE_THRESHOLD:
            log_warning(
                f"Alignment failed for {track_path.name} "
                f"(confidence: {confidence:.3f}). Setting offset to 0."
            )
            offset_ms = 0.0

        log_step(
            "Align",
            f"{track_path.name}: offset {offset_ms:+.1f}ms "
            f"(confidence: {confidence:.3f}, method: {method})",
        )

        aligned_tracks.append(
            AlignedTrack(
                path=str(track_path.relative_to(project_root)),
                offset_ms=offset_ms,
                duration_ms=track_info.duration_seconds * 1000,
                sample_rate=track_info.sample_rate,
                channels=track_info.channels,
                is_reference=False,
                alignment_confidence=round(confidence, 4),
                alignment_method=method,
            )
        )

    return AlignmentMap(
        reference_track=str(reference_path.relative_to(project_root)),
        tracks=aligned_tracks,
        common_timeline=CommonTimeline(
            start_ms=0.0,
            end_ms=max_duration * 1000,
        ),
    )


def _single_track_alignment(project_root: Path, track_path: Path) -> AlignmentMap:
    """Create a trivial alignment map for a single track."""
    info = probe_audio(track_path)
    log_step("Align", "Single track — no alignment needed")

    return AlignmentMap(
        reference_track=str(track_path.relative_to(project_root)),
        tracks=[
            AlignedTrack(
                path=str(track_path.relative_to(project_root)),
                offset_ms=0.0,
                duration_ms=info.duration_seconds * 1000,
                sample_rate=info.sample_rate,
                channels=info.channels,
                is_reference=True,
            )
        ],
        common_timeline=CommonTimeline(
            start_ms=0.0,
            end_ms=info.duration_seconds * 1000,
        ),
    )


def _load_downsampled(
    path: Path, target_rate: int, max_seconds: int
) -> "np.ndarray":
    """Load audio, downsample to target_rate, return first max_seconds."""
    import numpy as np
    import soundfile as sf

    audio, sr = sf.read(str(path), dtype="float32")

    # Use first channel if stereo
    if audio.ndim > 1:
        audio = audio[:, 0]

    # Truncate to max_seconds
    max_samples = int(sr * max_seconds)
    audio = audio[:max_samples]

    # Downsample via simple decimation
    if sr != target_rate:
        from scipy.signal import resample as scipy_resample

        num_samples = int(len(audio) * target_rate / sr)
        audio = scipy_resample(audio, num_samples).astype(np.float32)

    return audio


def _cross_correlate(
    ref: "np.ndarray", target: "np.ndarray", sample_rate: int
) -> tuple[float, float]:
    """Compute cross-correlation and return (offset_ms, confidence)."""
    import numpy as np
    from scipy.signal import correlate

    correlation = correlate(ref, target, mode="full")
    lag = int(np.argmax(np.abs(correlation))) - (len(target) - 1)

    offset_ms = (lag / sample_rate) * 1000

    # Normalized confidence
    denom = np.sqrt(np.sum(ref**2) * np.sum(target**2))
    confidence = float(np.max(np.abs(correlation)) / denom) if denom > 0 else 0.0

    return offset_ms, min(confidence, 1.0)


def _bandpass_filter(
    audio: "np.ndarray", sample_rate: int, low: float = 300.0, high: float = 3000.0
) -> "np.ndarray":
    """Apply a bandpass filter (speech frequency range)."""
    from scipy.signal import butter, sosfilt

    nyquist = sample_rate / 2.0
    low_norm = low / nyquist
    high_norm = high / nyquist

    # Clamp to valid range
    low_norm = max(low_norm, 0.001)
    high_norm = min(high_norm, 0.999)

    sos = butter(4, [low_norm, high_norm], btype="band", output="sos")
    return sosfilt(sos, audio)
