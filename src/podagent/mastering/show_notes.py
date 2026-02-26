"""Show notes finalization — Markdown to HTML."""

from __future__ import annotations

from pathlib import Path

from podagent.models.manifest import Manifest
from podagent.utils.progress import log_step, log_warning


def finalize_show_notes(
    summary_path: Path,
    manifest: Manifest,
    chapters: list[dict] | None = None,
) -> tuple[str, str]:
    """Finalize show notes as Markdown and HTML.

    Reads the summary from Module 2, adds header/footer, converts to HTML.
    Returns (markdown, html).
    """
    if summary_path.exists():
        summary = summary_path.read_text()
    else:
        log_warning("Content summary not found — generating minimal show notes")
        summary = f"Episode {manifest.project.episode_number} of {manifest.project.name}."

    # Build final Markdown
    host = next(
        (p.name for p in manifest.project.participants if p.role == "host"),
        manifest.project.participants[0].name if manifest.project.participants else "Host",
    )

    final_md = f"""# {manifest.project.title}

**{manifest.project.name}** — Episode {manifest.project.episode_number}
**Date**: {manifest.project.recording_date}
**Host**: {host}

---

{summary}

---

*Produced with PodAgent OS*
"""

    # Convert to HTML
    final_html = _markdown_to_html(final_md)

    log_step("ShowNotes", "Finalized Markdown + HTML")
    return final_md, final_html


def _markdown_to_html(md_text: str) -> str:
    """Convert Markdown to HTML."""
    try:
        import markdown
        return markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    except ImportError:
        log_warning("markdown package not installed — using basic HTML conversion")
        # Basic fallback
        html = md_text.replace("\n\n", "</p><p>")
        html = html.replace("\n", "<br>")
        return f"<p>{html}</p>"
