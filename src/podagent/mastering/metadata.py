"""ID3 metadata and chapter marker embedding via mutagen."""

from __future__ import annotations

from pathlib import Path

from podagent.utils.progress import log_step, log_warning


def embed_metadata(
    mp3_path: Path,
    metadata: dict,
    *,
    cover_art_bytes: bytes | None = None,
    cover_art_mime: str = "image/jpeg",
    chapters: list[dict] | None = None,
    duration_seconds: float = 0.0,
) -> None:
    """Embed ID3v2 tags, cover art, and chapter markers into MP3."""
    try:
        from mutagen.mp3 import MP3
        from mutagen.id3 import (
            ID3,
            TIT2,
            TPE1,
            TALB,
            TRCK,
            TDRC,
            TCON,
            COMM,
            APIC,
            CHAP,
            CTOC,
        )
    except ImportError:
        log_warning(
            "mutagen not installed — skipping metadata embedding. "
            "Install with: pip install podagent-os[mastering]"
        )
        return

    audio = MP3(str(mp3_path), ID3=ID3)

    try:
        audio.add_tags()
    except Exception:
        pass  # Tags already exist

    tags = audio.tags

    # Basic metadata
    tags.add(TIT2(encoding=3, text=[metadata.get("title", "")]))
    tags.add(TPE1(encoding=3, text=[metadata.get("artist", "")]))
    tags.add(TALB(encoding=3, text=[metadata.get("album", "")]))
    tags.add(TRCK(encoding=3, text=[str(metadata.get("track_number", ""))]))
    tags.add(TDRC(encoding=3, text=[str(metadata.get("year", ""))]))
    tags.add(TCON(encoding=3, text=[metadata.get("genre", "Podcast")]))

    comment = metadata.get("comment", "")
    if comment:
        tags.add(COMM(encoding=3, lang="eng", desc="", text=[comment]))

    log_step("Metadata", "ID3v2.4 tags embedded")

    # Cover art
    if cover_art_bytes:
        tags.add(APIC(
            encoding=3,
            mime=cover_art_mime,
            type=3,  # Front cover
            desc="Cover",
            data=cover_art_bytes,
        ))
        log_step("Metadata", f"Cover art embedded ({len(cover_art_bytes) / 1024:.0f} KB)")

    # Chapter markers
    if chapters:
        child_ids = [f"chap{i}" for i in range(len(chapters))]
        tags.add(CTOC(
            element_id="toc",
            flags=3,  # Top-level, ordered
            child_element_ids=child_ids,
            sub_frames=[],
        ))

        duration_ms = int(duration_seconds * 1000)
        for i, chapter in enumerate(chapters):
            start_ms = int(chapter["time"] * 1000)
            end_ms = (
                int(chapters[i + 1]["time"] * 1000)
                if i + 1 < len(chapters)
                else duration_ms
            )
            tags.add(CHAP(
                element_id=f"chap{i}",
                start_time=start_ms,
                end_time=end_ms,
                start_offset=0xFFFFFFFF,
                end_offset=0xFFFFFFFF,
                sub_frames=[TIT2(encoding=3, text=[chapter["title"]])],
            ))

        log_step("Metadata", f"{len(chapters)} chapter markers embedded")

    audio.save()
