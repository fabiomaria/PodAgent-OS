"""Assemble the publishing package."""

from __future__ import annotations

from pathlib import Path

from podagent.utils.io import write_atomic, write_json
from podagent.utils.progress import log_step


def assemble_package(
    output_dir: Path,
    *,
    show_notes_md: str,
    show_notes_html: str,
    metadata: dict,
    chapters: list[dict] | None = None,
    cover_art_bytes: bytes | None = None,
) -> None:
    """Write all deliverables to the publishing directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Show notes
    write_atomic(output_dir / "show-notes.md", show_notes_md)
    write_atomic(output_dir / "show-notes.html", show_notes_html)

    # Metadata
    write_json(output_dir / "metadata.json", metadata)

    # Cover art (resized copy)
    if cover_art_bytes:
        (output_dir / "cover-art.jpg").write_bytes(cover_art_bytes)

    # Chapter markers (simple text format)
    if chapters:
        lines = []
        for ch in chapters:
            time_s = ch.get("time", 0)
            m = int(time_s) // 60
            s = int(time_s) % 60
            lines.append(f"{m:02d}:{s:02d} {ch['title']}")
        write_atomic(output_dir / "chapters.txt", "\n".join(lines))

    log_step("Package", f"Publishing package assembled: {output_dir}")
