"""Filler word and false start detection."""

from __future__ import annotations

import re

from podagent.models.edl import Edit
from podagent.models.transcript import Segment
from podagent.utils.progress import log_step

# Filler word patterns (English)
FILLER_PATTERNS = [
    (r"\bum+\b", 0.95),
    (r"\buh+\b", 0.95),
    (r"\bah+\b", 0.90),
    (r"\ber+m?\b", 0.90),
    (r"\byou know\b", 0.80),
    (r"\blike\b(?=\s*,)", 0.80),  # "like" as filler, not comparison
    (r"\bbasically\b", 0.75),
    (r"\bactually\b", 0.70),
    (r"\bso+\b(?=\s*,)", 0.70),  # "so" as sentence filler
    (r"\bright\b(?=\s*[,?])", 0.70),  # "right?" as filler
    (r"\bi mean\b", 0.80),
]


def detect_fillers(
    segments: list[Segment],
    *,
    sensitivity: float = 0.7,
) -> list[Edit]:
    """Detect filler words in transcript segments.

    Returns a list of cut edits for filler regions.
    Fillers with confidence >= sensitivity are auto-applied.
    """
    edits: list[Edit] = []
    edit_counter = 0

    for seg in segments:
        text_lower = seg.text.lower()
        for pattern, base_confidence in FILLER_PATTERNS:
            matches = list(re.finditer(pattern, text_lower))
            if not matches:
                continue

            # Check if the entire segment is filler
            filler_ratio = sum(len(m.group()) for m in matches) / max(len(text_lower), 1)
            if filler_ratio < 0.3:
                # Less than 30% filler — skip (isolated filler in meaningful speech)
                continue

            confidence = base_confidence * min(filler_ratio * 2, 1.0)
            auto_apply = confidence >= sensitivity

            edit_counter += 1
            edits.append(Edit(
                id=f"filler-{edit_counter:03d}",
                type="cut",
                source_track=seg.source_track or "",
                source_start=seg.start,
                source_end=seg.end,
                reason="filler",
                confidence=round(confidence, 2),
                rationale=f"Filler words detected: '{seg.text[:80]}'",
                segments=[seg.id],
                auto_applied=auto_apply,
                review_flag=None if auto_apply else f"Confidence {confidence:.2f} below threshold {sensitivity}",
            ))

    log_step("Filler", f"Found {len(edits)} filler regions")
    return edits


def detect_false_starts(
    segments: list[Segment],
    *,
    min_gap_ms: float = 500,
    enabled: bool = True,
) -> list[Edit]:
    """Detect false starts: short abandoned utterances followed by a restart.

    A false start is when a speaker begins a sentence (< 3 words),
    pauses (> min_gap_ms), then starts again with similar words.
    """
    if not enabled:
        return []

    edits: list[Edit] = []
    edit_counter = 0

    for i in range(len(segments) - 1):
        seg = segments[i]
        next_seg = segments[i + 1]

        if seg.speaker != next_seg.speaker:
            continue
        if seg.word_count > 3:
            continue

        gap_ms = (next_seg.start - seg.end) * 1000
        if gap_ms < min_gap_ms:
            continue

        edit_counter += 1
        edits.append(Edit(
            id=f"false-start-{edit_counter:03d}",
            type="cut",
            source_track=seg.source_track or "",
            source_start=seg.start,
            source_end=seg.end,
            reason="false_start",
            confidence=0.85,
            rationale=f"False start ({seg.word_count} words, {gap_ms:.0f}ms gap): '{seg.text}'",
            segments=[seg.id],
            auto_applied=True,
        ))

    log_step("FalseStart", f"Found {len(edits)} false starts")
    return edits
