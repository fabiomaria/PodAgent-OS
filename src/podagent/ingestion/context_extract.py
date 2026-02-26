"""Step 5: Context extraction via Claude API (optional)."""

from __future__ import annotations

import json
import os
import time

from podagent.models.context import (
    ContextDocument,
    ContextMetadata,
    KeyQuote,
    ProperNoun,
    StructuralSegment,
    Topic,
)
from podagent.models.transcript import Segment
from podagent.utils.progress import log_step, log_warning


CONTEXT_PROMPT = """Analyze this podcast transcript and produce a structured analysis.

TRANSCRIPT:
{transcript_text}

Return a JSON object with exactly these fields:
1. "episode_summary": 2-3 sentence summary of the episode
2. "topics": array of objects with {{name, start_time, end_time, description}} for each distinct topic
3. "proper_nouns": array of objects with {{text, category, occurrences}} where category is one of: organization, product, person, place
4. "structural_segments": array of objects with {{type, label, start_time, end_time}} where type is one of: intro, main_topic, tangent, aside, outro. For tangents include a "confidence" field (0.0-1.0).
5. "key_quotes": array of objects with {{speaker, text, time}} for notable moments (max 5)

Return ONLY valid JSON, no markdown formatting."""


def extract_context(
    segments: list[Segment],
    *,
    model: str = "claude-sonnet-4-6",
    chunk_minutes: int = 15,
) -> ContextDocument | None:
    """Extract semantic context from transcript using Claude API.

    Returns None if API key is not available (degraded mode).
    For episodes > 30min, chunks transcript into segments with overlap.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log_warning(
            "ANTHROPIC_API_KEY not set — skipping context extraction. "
            "Pipeline will continue in degraded mode."
        )
        return None

    try:
        import anthropic
    except ImportError:
        log_warning(
            "anthropic package not installed — skipping context extraction. "
            "Install with: pip install podagent-os[llm]"
        )
        return None

    client = anthropic.Anthropic(api_key=api_key)

    # Format transcript as plain text (fewer tokens than JSON)
    transcript_text = _format_transcript(segments)
    total_duration = segments[-1].end if segments else 0

    # Decide chunking strategy
    if total_duration <= 30 * 60:  # < 30 minutes
        chunks = [transcript_text]
    else:
        chunks = _chunk_transcript(segments, chunk_minutes)

    log_step(
        "Context",
        f"Sending transcript to Claude ({len(chunks)} chunk(s), model: {model})",
    )

    start_time = time.time()
    total_prompt_tokens = 0
    total_completion_tokens = 0

    # Process each chunk
    all_results: list[dict] = []
    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            log_step("Context", f"  Processing chunk {i + 1}/{len(chunks)}...")

        prompt = CONTEXT_PROMPT.format(transcript_text=chunk)

        try:
            message = client.messages.create(
                model=model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            log_warning(f"Claude API error: {e}. Skipping context extraction.")
            return None

        total_prompt_tokens += message.usage.input_tokens
        total_completion_tokens += message.usage.output_tokens

        response_text = message.content[0].text
        parsed = _parse_llm_response(response_text)
        if parsed:
            all_results.append(parsed)

    if not all_results:
        log_warning("No valid context extracted from any chunk.")
        return None

    # Merge results from all chunks
    context = _merge_chunk_results(all_results)

    elapsed = time.time() - start_time
    context.metadata = ContextMetadata(
        llm_model=model,
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        processing_time_seconds=elapsed,
    )

    log_step(
        "Context",
        f"Extracted {len(context.topics)} topics, "
        f"{len(context.proper_nouns)} proper nouns, "
        f"{len(context.key_quotes)} key quotes "
        f"({elapsed:.1f}s)",
    )

    return context


def _format_transcript(segments: list[Segment]) -> str:
    """Format segments as readable plain text for LLM consumption."""
    lines = []
    for seg in segments:
        minutes = int(seg.start) // 60
        seconds = int(seg.start) % 60
        lines.append(f"[{minutes:02d}:{seconds:02d}] {seg.speaker}: {seg.text}")
    return "\n".join(lines)


def _chunk_transcript(
    segments: list[Segment],
    chunk_minutes: int,
    overlap_minutes: int = 1,
) -> list[str]:
    """Split transcript into chunks with overlap."""
    chunk_seconds = chunk_minutes * 60
    overlap_seconds = overlap_minutes * 60
    chunks: list[str] = []

    chunk_start = 0.0
    total_duration = segments[-1].end if segments else 0

    while chunk_start < total_duration:
        chunk_end = chunk_start + chunk_seconds
        chunk_segments = [
            s for s in segments
            if s.start >= chunk_start - overlap_seconds and s.end <= chunk_end + overlap_seconds
        ]
        if chunk_segments:
            chunks.append(_format_transcript(chunk_segments))
        chunk_start += chunk_seconds

    return chunks if chunks else [_format_transcript(segments)]


def _parse_llm_response(text: str) -> dict | None:
    """Parse JSON from LLM response, handling common formatting issues."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (fences)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        log_warning("Failed to parse LLM response as JSON")
        return None


def _merge_chunk_results(results: list[dict]) -> ContextDocument:
    """Merge context results from multiple chunks into one document."""
    if len(results) == 1:
        r = results[0]
        return ContextDocument(
            episode_summary=r.get("episode_summary", ""),
            topics=[Topic(**t) for t in r.get("topics", [])],
            proper_nouns=[ProperNoun(**n) for n in r.get("proper_nouns", [])],
            structural_segments=[
                StructuralSegment(**s) for s in r.get("structural_segments", [])
            ],
            key_quotes=[KeyQuote(**q) for q in r.get("key_quotes", [])],
        )

    # Multi-chunk merge
    all_topics = []
    all_nouns: dict[str, ProperNoun] = {}
    all_segments = []
    all_quotes = []
    summaries = []

    for r in results:
        summaries.append(r.get("episode_summary", ""))
        for t in r.get("topics", []):
            all_topics.append(Topic(**t))
        for n in r.get("proper_nouns", []):
            key = n.get("text", "").lower()
            if key in all_nouns:
                all_nouns[key].occurrences += n.get("occurrences", 0)
            else:
                all_nouns[key] = ProperNoun(**n)
        for s in r.get("structural_segments", []):
            all_segments.append(StructuralSegment(**s))
        for q in r.get("key_quotes", []):
            all_quotes.append(KeyQuote(**q))

    # Use first summary (covers the beginning of the episode)
    summary = summaries[0] if summaries else ""

    return ContextDocument(
        episode_summary=summary,
        topics=all_topics,
        proper_nouns=list(all_nouns.values()),
        structural_segments=all_segments,
        key_quotes=all_quotes[:5],  # Limit to 5
    )
