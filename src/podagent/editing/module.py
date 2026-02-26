"""Editing module — orchestrates all editing steps."""

from __future__ import annotations

import json
from pathlib import Path

from podagent.models.context import ContextDocument
from podagent.models.edl import Edit
from podagent.models.manifest import Manifest
from podagent.models.transcript import Segment, Transcript
from podagent.utils.io import read_json, write_atomic, write_json
from podagent.utils.progress import log_step, log_success, log_warning


class EditingModule:
    """Module 2: Narrative & Content Editing.

    Steps:
    1. Load and validate inputs (transcript, context, alignment)
    2. Filler & false start detection
    3. Silence detection
    4. Tangent detection via LLM (optional)
    5. Structural analysis
    6. Generate chapter markers
    7. Generate show notes
    8. Build EDL and write outputs
    """

    name = "editing"

    def validate_inputs(self, project_root: Path, manifest: Manifest) -> list[str]:
        errors = []
        transcript_path = project_root / manifest.files.transcript
        if not transcript_path.exists():
            errors.append(f"Transcript not found: {transcript_path}")
        alignment_path = project_root / manifest.files.alignment_map
        if not alignment_path.exists():
            errors.append(f"Alignment map not found: {alignment_path}")
        return errors

    def run(self, project_root: Path, manifest: Manifest) -> None:
        config = manifest.config.editing
        artifacts_dir = project_root / "artifacts" / "editing"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Load inputs
        transcript_data = read_json(project_root / manifest.files.transcript)
        transcript = Transcript(**transcript_data)
        segments = transcript.segments

        context: ContextDocument | None = None
        context_path = project_root / manifest.files.context_document
        if context_path.exists():
            context = ContextDocument(**read_json(context_path))
        else:
            log_warning("Context document not found — running in degraded mode")

        manifest.get_stage("editing").last_completed_step = "load"

        # Step 2: Filler detection
        from podagent.editing.filler import detect_false_starts, detect_fillers

        filler_edits = detect_fillers(segments, sensitivity=config.filler_sensitivity)
        false_start_edits = detect_false_starts(
            segments,
            enabled=config.detect_false_starts,
        )
        manifest.get_stage("editing").last_completed_step = "filler"

        # Step 3: Silence detection
        from podagent.editing.silence import detect_silences

        silence_edits = detect_silences(
            segments,
            min_duration_ms=config.min_silence_duration_ms,
            keep_ms=config.silence_keep_ms,
            speaker_turn_pause_ms=config.speaker_turn_pause_ms,
        )
        manifest.get_stage("editing").last_completed_step = "silence"

        # Step 4: Tangent detection (optional)
        from podagent.editing.tangent import detect_tangents

        tangent_edits = detect_tangents(
            segments,
            context,
            sensitivity=config.tangent_sensitivity,
            auto_cut_threshold=config.tangent_auto_cut_threshold,
            max_keep_seconds=config.max_tangent_keep_seconds,
            model=config.llm_model,
        )
        manifest.get_stage("editing").last_completed_step = "tangent"

        # Step 5: Structural analysis
        from podagent.editing.structure import analyze_structure

        structural_proposals = analyze_structure(segments, context)
        manifest.get_stage("editing").last_completed_step = "structure"

        # Combine all cut edits
        all_cuts = filler_edits + false_start_edits + silence_edits + tangent_edits

        # Safety: cap auto-cuts at 50% of episode duration
        total_duration = transcript.duration_seconds
        auto_cut_time = sum(e.duration for e in all_cuts if e.auto_applied)
        if total_duration > 0 and auto_cut_time / total_duration > 0.5:
            log_warning(
                f"Auto-cuts would remove {auto_cut_time:.0f}s "
                f"({auto_cut_time/total_duration*100:.0f}%) — "
                "capping at 50%. Flagging excess for review."
            )
            # Un-auto-apply cuts until under 50%
            budget = total_duration * 0.5
            used = 0.0
            for edit in sorted(all_cuts, key=lambda e: -(e.confidence or 0)):
                if edit.auto_applied:
                    if used + edit.duration <= budget:
                        used += edit.duration
                    else:
                        edit.auto_applied = False
                        edit.review_flag = "Auto-cut budget exceeded (>50% of episode)"

        # Step 6: Generate chapters
        from podagent.editing.chapters import generate_chapters

        chapters = generate_chapters(context, all_cuts, total_duration)
        manifest.get_stage("editing").last_completed_step = "chapters"

        # Step 7: Generate show notes
        from podagent.editing.show_notes import generate_show_notes

        show_notes_md = generate_show_notes(manifest, context, chapters)
        manifest.get_stage("editing").last_completed_step = "show_notes"

        # Step 8: Build EDL
        from podagent.editing.edl_builder import build_edl, write_edl_files

        episode_id = transcript.episode_id
        sidecar = build_edl(
            segments,
            all_cuts,
            episode_id=episode_id,
            frame_rate=config.edl_frame_rate,
            crossfade_duration_ms=config.crossfade_duration_ms,
        )

        # Write all outputs
        log_step("Write", "Writing artifacts to artifacts/editing/")

        write_edl_files(sidecar, artifacts_dir)

        # Write rationale log
        rationale = _build_rationale(
            all_cuts, filler_edits, false_start_edits, silence_edits, tangent_edits
        )
        write_json(artifacts_dir / "rationale.json", rationale)

        # Write show notes
        write_atomic(artifacts_dir / "summary.md", show_notes_md)

        auto_count = sum(1 for e in all_cuts if e.auto_applied)
        flagged_count = sum(1 for e in all_cuts if not e.auto_applied)

        log_success(
            f"Editing complete: {len(all_cuts)} edits "
            f"({auto_count} auto, {flagged_count} flagged), "
            f"{sidecar.time_removed_seconds:.0f}s removed "
            f"({sidecar.time_removed_percent:.1f}%)"
        )


def _build_rationale(
    all_cuts: list[Edit],
    fillers: list[Edit],
    false_starts: list[Edit],
    silences: list[Edit],
    tangents: list[Edit],
) -> dict:
    """Build the rationale log for Gate 2 review."""
    return {
        "version": "1.0",
        "summary": {
            "total_edits": len(all_cuts),
            "auto_applied": sum(1 for e in all_cuts if e.auto_applied),
            "flagged_for_review": sum(1 for e in all_cuts if not e.auto_applied),
            "time_removed_seconds": sum(e.duration for e in all_cuts),
            "breakdown": {
                "filler_removal": {
                    "count": len(fillers),
                    "time_removed": sum(e.duration for e in fillers),
                },
                "false_start_removal": {
                    "count": len(false_starts),
                    "time_removed": sum(e.duration for e in false_starts),
                },
                "silence_removal": {
                    "count": len(silences),
                    "time_removed": sum(e.duration for e in silences),
                },
                "tangent_removal": {
                    "count": len(tangents),
                    "time_removed": sum(e.duration for e in tangents),
                },
            },
        },
        "edits": [
            {
                "edit_id": e.id,
                "type": e.reason or "unknown",
                "time": f"{int(e.source_start)//60:02d}:{int(e.source_start)%60:02d} - "
                        f"{int(e.source_end)//60:02d}:{int(e.source_end)%60:02d}",
                "duration": f"{e.duration:.1f}s",
                "confidence": e.confidence,
                "rationale": e.rationale,
                "auto_applied": e.auto_applied,
            }
            for e in all_cuts
        ],
    }
