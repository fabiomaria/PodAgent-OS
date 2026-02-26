"""Silence detection and trimming."""

from __future__ import annotations

from podagent.models.edl import Edit
from podagent.models.transcript import Segment
from podagent.utils.progress import log_step


def detect_silences(
    segments: list[Segment],
    *,
    min_duration_ms: float = 800,
    keep_ms: float = 300,
    speaker_turn_pause_ms: float = 500,
) -> list[Edit]:
    """Detect extended silences (gaps between segments) to trim.

    Rules:
    - Silences < min_duration_ms: keep entirely
    - Same-speaker silences: trim to keep_ms
    - Between-speaker silences: trim to speaker_turn_pause_ms
    - Confidence is always 1.0 (objective measurement)
    """
    edits: list[Edit] = []
    edit_counter = 0

    for i in range(len(segments) - 1):
        gap_start = segments[i].end
        gap_end = segments[i + 1].start
        gap_ms = (gap_end - gap_start) * 1000

        if gap_ms <= min_duration_ms:
            continue

        between_speakers = segments[i].speaker != segments[i + 1].speaker
        target_ms = speaker_turn_pause_ms if between_speakers else keep_ms

        # Trim region: keep target_ms of silence, cut the rest
        trim_start = gap_start + (target_ms / 1000)
        trim_end = gap_end

        if trim_start >= trim_end:
            continue

        trimmed_ms = (trim_end - trim_start) * 1000

        edit_counter += 1
        edits.append(Edit(
            id=f"silence-{edit_counter:03d}",
            type="cut",
            source_track=segments[i].source_track or "",
            source_start=trim_start,
            source_end=trim_end,
            reason="silence",
            confidence=1.0,
            rationale=(
                f"Silence trimmed: {gap_ms:.0f}ms → {target_ms:.0f}ms "
                f"({'between speakers' if between_speakers else 'same speaker'})"
            ),
            auto_applied=True,
        ))

    total_trimmed = sum(e.duration for e in edits)
    log_step(
        "Silence",
        f"Found {len(edits)} long silences ({total_trimmed:.1f}s total trimmed)",
    )
    return edits
