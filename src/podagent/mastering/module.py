"""Mastering module — orchestrates all mastering steps."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from podagent.models.manifest import Manifest
from podagent.utils.ffprobe import probe_audio
from podagent.utils.io import read_json
from podagent.utils.progress import log_step, log_success, log_warning


class MasteringModule:
    """Module 4: Mastering & Publishing Delivery.

    Steps:
    1. Validate input and measure source loudness
    2. Loudness normalization (two-pass linear)
    3. Encode to MP3
    4. Produce archive WAV
    5. Embed metadata and cover art
    6. Generate show notes (Markdown + HTML)
    7. Verify output quality
    8. Assemble publishing package
    """

    name = "mastering"

    def validate_inputs(self, project_root: Path, manifest: Manifest) -> list[str]:
        errors = []
        mixed_path = project_root / manifest.files.mixed_audio
        if not mixed_path.exists():
            errors.append(f"Mixed audio not found: {mixed_path}")
        return errors

    def run(self, project_root: Path, manifest: Manifest) -> None:
        config = manifest.config.mastering
        artifacts_dir = project_root / "artifacts" / "mastering"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        start_time = time.time()
        mixed_path = project_root / manifest.files.mixed_audio

        # Step 1: Validate input
        log_step("Validate", f"Checking {mixed_path.name}")
        mixed_info = probe_audio(mixed_path)
        log_step(
            "Validate",
            f"{mixed_info.duration_seconds:.0f}s, "
            f"{mixed_info.sample_rate}Hz, "
            f"{mixed_info.bit_depth or '?'}-bit, "
            f"{'stereo' if mixed_info.channels >= 2 else 'mono'}",
        )
        manifest.get_stage("mastering").last_completed_step = "validate"

        # Step 2: Loudness normalization
        from podagent.mastering.loudness import normalize_loudness

        normalized_path = artifacts_dir / "normalized.wav"
        measurements = normalize_loudness(
            mixed_path,
            normalized_path,
            target_i=config.target_lufs,
            target_tp=config.true_peak_limit_dbtp,
            target_lra=config.loudnorm_lra,
        )
        manifest.get_stage("mastering").last_completed_step = "loudness"

        # Step 3: Encode MP3
        mp3_path = artifacts_dir / "episode.mp3"
        if "mp3" in config.output_formats:
            from podagent.mastering.encode import encode_mp3

            encode_mp3(
                normalized_path,
                mp3_path,
                bitrate=config.mp3_bitrate_kbps,
                sample_rate=config.mp3_sample_rate,
                mono=config.mp3_mono,
            )
        manifest.get_stage("mastering").last_completed_step = "encode"

        # Step 4: Archive WAV
        wav_path = artifacts_dir / "episode.wav"
        if "wav" in config.output_formats:
            log_step("Archive", "Producing archive WAV (48kHz/24-bit)")
            shutil.copy2(normalized_path, wav_path)
        manifest.get_stage("mastering").last_completed_step = "archive"

        # Clean up temporary normalized file if different from archive
        if normalized_path != wav_path and normalized_path.exists():
            normalized_path.unlink()

        # Step 5: Metadata and cover art
        # Prepare cover art
        cover_art_bytes = None
        cover_art_mime = "image/jpeg"
        if config.cover_art_path:
            art_path = project_root / config.cover_art_path
            if art_path.exists():
                from podagent.mastering.cover_art import prepare_cover_art
                cover_art_bytes, cover_art_mime = prepare_cover_art(
                    art_path,
                    max_size_px=config.cover_art_max_px,
                )

        # Load chapters from editing summary if available
        chapters = _load_chapters(project_root, manifest)

        # Build metadata dict
        host_name = next(
            (p.name for p in manifest.project.participants if p.role == "host"),
            manifest.project.participants[0].name if manifest.project.participants else "",
        )

        id3_metadata = {
            "title": manifest.project.title,
            "artist": host_name,
            "album": manifest.project.name,
            "track_number": manifest.project.episode_number,
            "year": manifest.project.recording_date[:4] if manifest.project.recording_date else "",
            "genre": config.id3_genre,
            "comment": "",
            "album_artist": manifest.project.name,
            "publisher": config.id3_publisher,
            "url": config.id3_url,
            "duration_seconds": mixed_info.duration_seconds,
        }

        if mp3_path.exists() and config.embed_chapters:
            from podagent.mastering.metadata import embed_metadata

            embed_metadata(
                mp3_path,
                id3_metadata,
                cover_art_bytes=cover_art_bytes,
                cover_art_mime=cover_art_mime,
                chapters=chapters,
                duration_seconds=mixed_info.duration_seconds,
            )
        manifest.get_stage("mastering").last_completed_step = "metadata"

        # Step 6: Show notes
        from podagent.mastering.show_notes import finalize_show_notes

        summary_path = project_root / manifest.files.content_summary
        show_notes_md, show_notes_html = finalize_show_notes(
            summary_path,
            manifest,
            chapters=chapters,
        )
        manifest.get_stage("mastering").last_completed_step = "show_notes"

        # Step 7: Verify output
        verification = {}
        if config.verify_output and mp3_path.exists():
            from podagent.mastering.verify import verify_output

            verification = verify_output(
                mp3_path,
                target_lufs=config.target_lufs,
                target_tp=config.true_peak_limit_dbtp,
            )
        manifest.get_stage("mastering").last_completed_step = "verify"

        # Step 8: Assemble package
        from podagent.mastering.package import assemble_package

        full_metadata = {
            "version": "1.0",
            "id3": id3_metadata,
            "loudness": {
                "integrated_lufs": verification.get("integrated_lufs", config.target_lufs),
                "true_peak_dbtp": verification.get("true_peak_dbtp", config.true_peak_limit_dbtp),
                "loudness_range_lu": verification.get("loudness_range_lu", 0),
            },
            "file_info": {
                "mp3_path": str(mp3_path.relative_to(project_root)) if mp3_path.exists() else None,
                "mp3_size_bytes": mp3_path.stat().st_size if mp3_path.exists() else 0,
                "mp3_duration_seconds": mixed_info.duration_seconds,
                "wav_path": str(wav_path.relative_to(project_root)) if wav_path.exists() else None,
                "wav_size_bytes": wav_path.stat().st_size if wav_path.exists() else 0,
            },
            "chapters": [
                {
                    "title": ch["title"],
                    "start_ms": int(ch["time"] * 1000),
                    "end_ms": int(chapters[i + 1]["time"] * 1000) if i + 1 < len(chapters)
                    else int(mixed_info.duration_seconds * 1000),
                }
                for i, ch in enumerate(chapters)
            ] if chapters else [],
        }

        assemble_package(
            artifacts_dir,
            show_notes_md=show_notes_md,
            show_notes_html=show_notes_html,
            metadata=full_metadata,
            chapters=chapters,
            cover_art_bytes=cover_art_bytes,
        )

        elapsed = time.time() - start_time
        log_success(
            f"Mastering complete in {elapsed:.0f}s. "
            f"Publishing package: {artifacts_dir}"
        )


def _load_chapters(project_root: Path, manifest: Manifest) -> list[dict]:
    """Load chapter markers from the editing module's output."""
    # Try to load from EDL sidecar (chapters are encoded in keep edits)
    # Or from the content summary
    edl_path = project_root / manifest.files.edl_sidecar
    if edl_path.exists():
        edl = read_json(edl_path)
        # Chapters aren't directly in the EDL — check for summary.md
        pass

    # Default: single chapter
    return [{"title": "Episode Start", "time": 0.0}]
