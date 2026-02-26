"""Chapter marker generation."""

from __future__ import annotations

from podagent.models.context import ContextDocument
from podagent.models.edl import Edit
from podagent.utils.progress import log_step


def generate_chapters(
    context: ContextDocument | None,
    cut_edits: list[Edit],
    total_duration: float,
) -> list[dict]:
    """Generate chapter markers from context document topics.

    Adjusts timestamps to account for removed segments.
    """
    chapters = [{"title": "Introduction", "time": 0.0}]

    if not context or not context.topics:
        log_step("Chapters", "No context — using single chapter")
        return chapters

    for topic in context.topics:
        edited_time = _map_to_edited_timeline(topic.start_time, cut_edits)
        if edited_time is not None and edited_time > 0:
            chapters.append({
                "title": topic.name,
                "time": edited_time,
            })

    # Deduplicate chapters that are too close together (< 30s apart)
    deduped = [chapters[0]]
    for ch in chapters[1:]:
        if ch["time"] - deduped[-1]["time"] >= 30:
            deduped.append(ch)

    log_step("Chapters", f"Generated {len(deduped)} chapter markers")
    return deduped


def _map_to_edited_timeline(
    original_time: float,
    cut_edits: list[Edit],
) -> float | None:
    """Map an original timestamp to the edited timeline position.

    Accounts for all cuts before this timestamp.
    """
    offset = 0.0
    for edit in cut_edits:
        if edit.source_end <= original_time:
            # This cut happens entirely before our timestamp
            offset += edit.duration
        elif edit.source_start < original_time < edit.source_end:
            # Our timestamp falls within a cut region
            return None  # This point was cut

    return original_time - offset
