"""Ingestion module — orchestrates all ingestion steps."""

from __future__ import annotations

from pathlib import Path

from podagent.models.alignment import AlignmentMap
from podagent.models.manifest import Manifest
from podagent.models.transcript import Transcript
from podagent.utils.io import write_json
from podagent.utils.progress import log_step, log_success


class IngestionModule:
    """Module 1: Ingestion & Context Mapping.

    Steps:
    1. Validate and catalog input audio files
    2. Transcribe each track with faster-whisper
    3. Speaker diarization (multi-track VAD or pyannote)
    4. Multi-track alignment via cross-correlation
    5. Merge per-track transcripts into unified timeline
    6. LLM context extraction (optional)
    7. Write artifacts and update manifest
    """

    name = "ingestion"

    def validate_inputs(self, project_root: Path, manifest: Manifest) -> list[str]:
        """Check that required inputs are present."""
        errors = []
        if not manifest.project.participants:
            errors.append("No participants defined in manifest")
        for p in manifest.project.participants:
            track_path = project_root / p.track
            if not track_path.exists():
                errors.append(f"Track not found: {track_path}")
        return errors

    def run(self, project_root: Path, manifest: Manifest) -> None:
        """Execute the full ingestion pipeline."""
        config = manifest.config.ingestion
        artifacts_dir = project_root / "artifacts" / "ingestion"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Validate tracks
        from podagent.ingestion.validate import validate_tracks

        track_infos = validate_tracks(project_root, manifest)
        manifest.get_stage("ingestion").last_completed_step = "validate"

        # Resolve track paths
        track_paths = [
            project_root / p.track for p in manifest.project.participants
        ]
        speakers = [p.name for p in manifest.project.participants]

        # Step 2: Transcribe
        from podagent.ingestion.transcribe import transcribe_tracks

        per_track_segments, tx_metadata = transcribe_tracks(
            track_paths,
            speakers,
            model_size=config.transcription_model,
            device=config.transcription_device,
            language=config.transcription_language,
            vad_enabled=config.vad_enabled,
            vad_min_silence_ms=config.vad_min_silence_ms,
        )
        manifest.get_stage("ingestion").last_completed_step = "transcribe"

        # Step 3: Diarize (multi-track mode uses per-track VAD)
        from podagent.ingestion.diarize import (
            diarize_multi_track,
            diarize_single_track,
            get_diarization_strategy,
        )

        strategy = get_diarization_strategy(manifest)
        if strategy == "multi-track":
            diarize_multi_track(track_paths, speakers)
        else:
            diarize_single_track(
                track_paths[0],
                num_speakers=config.diarization_num_speakers
                or len(manifest.project.participants),
            )
        manifest.get_stage("ingestion").last_completed_step = "diarize"

        # Step 4: Align tracks
        from podagent.ingestion.align import align_tracks

        alignment = align_tracks(
            project_root,
            track_paths,
            segment_seconds=config.alignment_segment_seconds,
        )
        manifest.get_stage("ingestion").last_completed_step = "align"

        # Step 5: Merge transcripts
        from podagent.ingestion.merge import merge_transcripts

        # Build offset map: speaker → offset_ms
        track_offsets = {}
        for track_info in alignment.tracks:
            # Find speaker for this track
            for p in manifest.project.participants:
                if p.track == track_info.path:
                    track_offsets[p.name] = track_info.offset_ms
                    break

        merged_segments = merge_transcripts(per_track_segments, track_offsets)
        manifest.get_stage("ingestion").last_completed_step = "merge"

        # Build transcript model
        total_duration = max(
            (s.end for s in merged_segments), default=0.0
        )
        total_words = sum(s.word_count for s in merged_segments)

        tx_metadata.word_count = total_words
        tx_metadata.segment_count = len(merged_segments)

        episode_id = (
            f"{manifest.project.name.lower().replace(' ', '-')}"
            f"-ep{manifest.project.episode_number}"
        )

        transcript = Transcript(
            episode_id=episode_id,
            duration_seconds=total_duration,
            segments=merged_segments,
            metadata=tx_metadata,
        )

        # Step 6: Context extraction (optional)
        from podagent.ingestion.context_extract import extract_context

        context = extract_context(
            merged_segments,
            model=config.llm_model,
            chunk_minutes=config.llm_chunk_minutes,
        )
        manifest.get_stage("ingestion").last_completed_step = "context"

        # Step 7: Write artifacts
        log_step("Write", "Writing artifacts to artifacts/ingestion/")

        write_json(
            artifacts_dir / "transcript.json",
            transcript.model_dump(mode="json"),
        )
        write_json(
            artifacts_dir / "alignment.json",
            alignment.model_dump(mode="json"),
        )
        if context:
            write_json(
                artifacts_dir / "context.json",
                context.model_dump(mode="json"),
            )

        log_success(
            f"Ingestion complete: {len(merged_segments)} segments, "
            f"{total_words} words"
        )
