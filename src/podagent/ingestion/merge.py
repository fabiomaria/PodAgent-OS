"""Step 3.5: Merge per-track transcripts into unified timeline."""

from __future__ import annotations

from podagent.models.transcript import Segment
from podagent.utils.progress import log_step


def merge_transcripts(
    per_track_segments: dict[str, list[Segment]],
    track_offsets: dict[str, float] | None = None,
    *,
    merge_gap_ms: float = 200.0,
) -> list[Segment]:
    """Merge per-track transcripts into a single interleaved timeline.

    Steps:
    1. Apply alignment offsets to each track's timestamps
    2. Collect all segments into one list
    3. Sort by start time
    4. Mark overlapping segments
    5. Merge adjacent same-speaker segments separated by < merge_gap_ms
    6. Assign sequential segment IDs
    """
    all_segments: list[Segment] = []

    for speaker, segments in per_track_segments.items():
        offset_s = 0.0
        if track_offsets and speaker in track_offsets:
            offset_s = track_offsets[speaker] / 1000.0  # ms → s

        for seg in segments:
            adjusted = seg.model_copy(update={
                "start": seg.start + offset_s,
                "end": seg.end + offset_s,
                "words": [
                    w.model_copy(update={
                        "start": w.start + offset_s,
                        "end": w.end + offset_s,
                    })
                    for w in seg.words
                ],
            })
            all_segments.append(adjusted)

    # Sort by start time
    all_segments.sort(key=lambda s: s.start)

    # Merge adjacent same-speaker segments with small gaps
    merged = _merge_adjacent(all_segments, merge_gap_ms)

    # Assign sequential IDs
    for i, seg in enumerate(merged, start=1):
        seg.id = f"seg-{i:03d}"

    log_step(
        "Merge",
        f"Merged {sum(len(s) for s in per_track_segments.values())} segments "
        f"→ {len(merged)} unified segments",
    )

    return merged


def _merge_adjacent(
    segments: list[Segment],
    max_gap_ms: float,
) -> list[Segment]:
    """Merge adjacent segments from the same speaker if gap < max_gap_ms."""
    if not segments:
        return []

    merged: list[Segment] = [segments[0].model_copy()]

    for seg in segments[1:]:
        prev = merged[-1]
        gap_ms = (seg.start - prev.end) * 1000

        if (
            seg.speaker == prev.speaker
            and gap_ms < max_gap_ms
            and gap_ms >= 0
        ):
            # Merge: extend previous segment
            merged[-1] = prev.model_copy(update={
                "end": seg.end,
                "text": prev.text + " " + seg.text,
                "words": prev.words + seg.words,
            })
        else:
            merged.append(seg.model_copy())

    return merged
