"""Tangent detection via Claude API (optional)."""

from __future__ import annotations

import json
import os

from podagent.models.context import ContextDocument
from podagent.models.edl import Edit
from podagent.models.transcript import Segment
from podagent.utils.progress import log_step, log_warning

TANGENT_SYSTEM_PROMPT = """You are an expert podcast editor. Your job is to identify \
tangents (off-topic digressions) in a podcast transcript. A tangent is a section \
where the conversation drifts away from the episode's main topics and does not \
contribute to the core narrative.

You will receive:
1. The episode's main topics (from the context document)
2. The full transcript with timestamps

For each tangent you identify, provide:
- start_time and end_time (in seconds)
- A confidence score (0.0-1.0)
- A brief rationale explaining why it's off-topic
- tangent_type: "hard" (clearly off-topic) or "soft" (marginally related)

Do NOT flag:
- Humorous asides that last < 30 seconds (these add personality)
- Personal anecdotes that illustrate the main topic
- Brief digressions that the speakers self-correct from quickly

Return a JSON array of tangent objects with fields: \
start_time, end_time, confidence, rationale, tangent_type"""


def detect_tangents(
    segments: list[Segment],
    context: ContextDocument | None,
    *,
    sensitivity: float = 0.5,
    auto_cut_threshold: float = 0.85,
    max_keep_seconds: int = 30,
    model: str = "claude-sonnet-4-6",
    chunk_minutes: int = 15,
) -> list[Edit]:
    """Detect tangents using LLM analysis.

    Returns empty list if:
    - No context document available
    - No API key
    - anthropic not installed
    """
    if not context or not context.topics:
        log_warning("No context document or topics — skipping tangent detection")
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log_warning("ANTHROPIC_API_KEY not set — skipping tangent detection")
        return []

    try:
        import anthropic
    except ImportError:
        log_warning("anthropic not installed — skipping tangent detection")
        return []

    client = anthropic.Anthropic(api_key=api_key)

    # Format topics
    topics_text = "\n".join(
        f"- {t.name}: {t.description} ({t.start_time:.0f}s - {t.end_time:.0f}s)"
        for t in context.topics
    )

    # Format transcript
    transcript_text = "\n".join(
        f"[{int(s.start)//60:02d}:{int(s.start)%60:02d}] {s.speaker}: {s.text}"
        for s in segments
    )

    # Chunk if needed
    total_duration = segments[-1].end if segments else 0
    chunk_seconds = chunk_minutes * 60

    all_tangents: list[dict] = []

    if total_duration <= chunk_seconds * 2:
        # Single chunk
        tangents = _call_tangent_api(
            client, model, topics_text, transcript_text
        )
        all_tangents.extend(tangents)
    else:
        # Multiple chunks
        chunk_start = 0.0
        chunk_idx = 0
        while chunk_start < total_duration:
            chunk_end = chunk_start + chunk_seconds
            chunk_segs = [
                s for s in segments if s.start >= chunk_start and s.end <= chunk_end + 60
            ]
            if chunk_segs:
                chunk_text = "\n".join(
                    f"[{int(s.start)//60:02d}:{int(s.start)%60:02d}] {s.speaker}: {s.text}"
                    for s in chunk_segs
                )
                chunk_idx += 1
                log_step("Tangent", f"  Processing chunk {chunk_idx}...")
                tangents = _call_tangent_api(
                    client, model, topics_text, chunk_text
                )
                all_tangents.extend(tangents)
            chunk_start += chunk_seconds

    # Convert to edits
    edits: list[Edit] = []
    for i, tangent in enumerate(all_tangents, start=1):
        confidence = tangent.get("confidence", 0.5)
        duration = tangent.get("end_time", 0) - tangent.get("start_time", 0)

        # Skip tangents below minimum confidence
        if confidence < 0.60:
            continue

        # Skip short tangents (personality preservation)
        if duration < max_keep_seconds:
            continue

        auto_apply = confidence >= auto_cut_threshold and sensitivity >= 0.5

        edits.append(Edit(
            id=f"tangent-{i:03d}",
            type="cut",
            source_track="",  # Applies to all tracks
            source_start=tangent.get("start_time", 0),
            source_end=tangent.get("end_time", 0),
            reason="tangent",
            confidence=round(confidence, 2),
            rationale=tangent.get("rationale", "Off-topic digression"),
            auto_applied=auto_apply,
            review_flag=(
                None if auto_apply
                else f"Confidence {confidence:.2f} below auto-cut threshold {auto_cut_threshold}"
            ),
        ))

    log_step("Tangent", f"Found {len(edits)} tangents ({len(all_tangents)} raw)")
    return edits


def _call_tangent_api(
    client: "anthropic.Anthropic",
    model: str,
    topics_text: str,
    transcript_text: str,
) -> list[dict]:
    """Call Claude API for tangent detection."""
    try:
        message = client.messages.create(
            model=model,
            max_tokens=4096,
            system=TANGENT_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"EPISODE TOPICS:\n{topics_text}\n\nTRANSCRIPT:\n{transcript_text}\n\nIdentify all tangents. Return JSON array.",
            }],
        )
    except Exception as e:
        log_warning(f"Tangent detection API error: {e}")
        return []

    text = message.content[0].text.strip()
    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        return []
    except json.JSONDecodeError:
        log_warning("Failed to parse tangent detection response as JSON")
        return []
