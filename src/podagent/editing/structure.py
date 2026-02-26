"""Structural editing analysis."""

from __future__ import annotations

from podagent.models.context import ContextDocument
from podagent.models.transcript import Segment
from podagent.utils.progress import log_step


def analyze_structure(
    segments: list[Segment],
    context: ContextDocument | None,
) -> list[dict]:
    """Analyze episode structure and propose improvements.

    All proposals require human approval (never auto-applied).
    """
    if not context:
        return []

    proposals = []

    # 1. Long intro detection
    intro = next(
        (s for s in context.structural_segments if s.type == "intro"),
        None,
    )
    if intro and (intro.end_time - intro.start_time) > 120:
        duration = intro.end_time - intro.start_time
        proposals.append({
            "type": "trim_intro",
            "rationale": f"Intro is {duration:.0f}s (>2 min). Consider trimming to <60s.",
            "suggestion": "Move the first substantive topic mention earlier.",
            "start_time": intro.start_time,
            "end_time": intro.end_time,
            "auto_applied": False,
        })

    # 2. Abrupt ending detection
    outro = next(
        (s for s in context.structural_segments if s.type == "outro"),
        None,
    )
    total_duration = segments[-1].end if segments else 0
    if not outro or (total_duration - outro.start_time) < 10:
        proposals.append({
            "type": "missing_outro",
            "rationale": "No clear outro detected. Episode may end abruptly.",
            "suggestion": "Consider adding a closing segment.",
            "auto_applied": False,
        })

    # 3. Split topic detection — same topic appears non-contiguously
    if context.topics:
        topic_names = [t.name for t in context.topics]
        seen = {}
        for i, name in enumerate(topic_names):
            if name in seen and i - seen[name] > 1:
                proposals.append({
                    "type": "split_topic",
                    "rationale": f"Topic '{name}' is split across non-contiguous segments.",
                    "suggestion": "Consider consolidating related segments.",
                    "auto_applied": False,
                })
            seen[name] = i

    log_step("Structure", f"Found {len(proposals)} structural proposals")
    return proposals
