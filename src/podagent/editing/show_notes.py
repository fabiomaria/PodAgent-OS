"""Show notes generation via Claude API (optional)."""

from __future__ import annotations

import os

from podagent.models.context import ContextDocument
from podagent.models.manifest import Manifest
from podagent.utils.progress import log_step, log_warning


def generate_show_notes(
    manifest: Manifest,
    context: ContextDocument | None,
    chapters: list[dict],
) -> str:
    """Generate show notes as Markdown.

    Uses Claude API if available, otherwise builds from context document.
    """
    # Try LLM-powered generation
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key and context:
        try:
            return _generate_via_llm(manifest, context, chapters, api_key)
        except Exception as e:
            log_warning(f"LLM show notes generation failed: {e}. Using template.")

    # Fallback: template-based generation
    return _generate_template(manifest, context, chapters)


def _generate_via_llm(
    manifest: Manifest,
    context: ContextDocument,
    chapters: list[dict],
    api_key: str,
) -> str:
    """Generate show notes via Claude API."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    topics_text = "\n".join(f"- {t.name}: {t.description}" for t in context.topics)
    quotes_text = "\n".join(
        f'- "{q.text}" — {q.speaker}, {_format_time(q.time)}' for q in context.key_quotes
    )
    chapters_text = "\n".join(
        f"- {_format_time(ch['time'])} — {ch['title']}" for ch in chapters
    )

    model = manifest.config.editing.llm_model

    log_step("ShowNotes", f"Generating via Claude ({model})...")

    message = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"""Write podcast show notes for this episode.

EPISODE TITLE: {manifest.project.title}
SHOW NAME: {manifest.project.name}
EPISODE NUMBER: {manifest.project.episode_number}
EPISODE SUMMARY: {context.episode_summary}
TOPICS: {topics_text}
KEY QUOTES: {quotes_text}
CHAPTERS: {chapters_text}

Include:
1. A 2-3 sentence description suitable for a podcast feed
2. Chapter timestamps
3. Key quotes (attributed, with timestamps)
4. Keywords for SEO

Format as Markdown. Do not include a title header (it will be added separately).""",
        }],
    )

    return message.content[0].text


def _generate_template(
    manifest: Manifest,
    context: ContextDocument | None,
    chapters: list[dict],
) -> str:
    """Generate show notes using a simple template."""
    lines = []

    # Summary
    if context and context.episode_summary:
        lines.append(context.episode_summary)
    else:
        lines.append(f"Episode {manifest.project.episode_number} of {manifest.project.name}.")

    lines.append("")

    # Chapters
    if chapters:
        lines.append("## Chapters")
        for ch in chapters:
            lines.append(f"- {_format_time(ch['time'])} — {ch['title']}")
        lines.append("")

    # Key quotes
    if context and context.key_quotes:
        lines.append("## Key Quotes")
        for q in context.key_quotes:
            lines.append(f'> "{q.text}"')
            lines.append(f"> — {q.speaker}, {_format_time(q.time)}")
            lines.append("")

    # Keywords
    if context and context.proper_nouns:
        keywords = [n.text for n in context.proper_nouns[:10]]
        lines.append("## Keywords")
        lines.append(", ".join(keywords))

    return "\n".join(lines)


def _format_time(seconds: float) -> str:
    """Format seconds as MM:SS."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"
