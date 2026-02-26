"""Gate review system — CLI prompts and file-based review."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from podagent.models.manifest import Manifest
from podagent.utils.io import read_yaml, write_yaml
from podagent.utils.progress import log, log_success

console = Console()


def present_gate(
    project_root: Path, manifest: Manifest, stage_name: str
) -> bool:
    """Present a review gate to the user. Returns True if approved."""
    console.print()
    console.print(f"[bold yellow]═══ Gate Review: {stage_name} ═══[/bold yellow]")
    console.print()

    if stage_name == "ingestion":
        _show_ingestion_gate(project_root, manifest)
    elif stage_name == "editing":
        _show_editing_gate(project_root, manifest)
    elif stage_name == "mixing":
        _show_mixing_gate(project_root, manifest)
    elif stage_name == "mastering":
        _show_mastering_gate(project_root, manifest)

    console.print()
    return click.confirm("Approve this gate?", default=True)


def _show_ingestion_gate(project_root: Path, manifest: Manifest) -> None:
    """Show ingestion gate review information."""
    transcript_path = project_root / manifest.files.transcript
    alignment_path = project_root / manifest.files.alignment_map
    context_path = project_root / manifest.files.context_document

    # Transcript summary
    if transcript_path.exists():
        with open(transcript_path) as f:
            transcript = json.load(f)
        segments = transcript.get("segments", [])
        meta = transcript.get("metadata", {})
        speakers = sorted(set(s.get("speaker", "?") for s in segments))

        table = Table(title="Transcript Summary", show_lines=True)
        table.add_column("Metric", style="bold")
        table.add_column("Value")
        table.add_row("Segments", str(len(segments)))
        table.add_row("Words", str(meta.get("word_count", "?")))
        table.add_row("Duration", f"{transcript.get('duration_seconds', 0):.0f}s")
        table.add_row("Speakers", ", ".join(speakers))
        table.add_row("Language", transcript.get("language", "?"))
        console.print(table)
    else:
        console.print("[yellow]Transcript not found[/yellow]")

    # Alignment summary
    if alignment_path.exists():
        with open(alignment_path) as f:
            alignment = json.load(f)
        tracks = alignment.get("tracks", [])
        console.print()
        console.print("[bold]Alignment:[/bold]")
        for t in tracks:
            conf = t.get("alignment_confidence")
            conf_str = f" (confidence: {conf:.3f})" if conf is not None else ""
            console.print(
                f"  {Path(t['path']).name}: offset {t['offset_ms']:.0f}ms{conf_str}"
            )

    # Context summary
    if context_path.exists():
        with open(context_path) as f:
            context = json.load(f)
        topics = context.get("topics", [])
        nouns = context.get("proper_nouns", [])
        console.print()
        console.print("[bold]Context:[/bold]")
        console.print(f"  Summary: {context.get('episode_summary', 'N/A')[:200]}")
        console.print(f"  Topics: {len(topics)}")
        for t in topics[:5]:
            console.print(f"    - {t['name']}")
        console.print(f"  Proper nouns: {len(nouns)}")

    # Show artifact paths for manual review
    console.print()
    console.print("[dim]Review artifacts:[/dim]")
    for label, path in [
        ("Transcript", transcript_path),
        ("Alignment", alignment_path),
        ("Context", context_path),
    ]:
        exists = "✓" if path.exists() else "✗"
        console.print(f"  [{exists}] {label}: {path}")


def _show_editing_gate(project_root: Path, manifest: Manifest) -> None:
    """Show editing gate review information."""
    edl_path = project_root / manifest.files.edl_sidecar
    rationale_path = project_root / manifest.files.edit_rationale
    summary_path = project_root / manifest.files.content_summary

    if edl_path.exists():
        with open(edl_path) as f:
            edl = json.load(f)

        table = Table(title="Edit Summary", show_lines=True)
        table.add_column("Metric", style="bold")
        table.add_column("Value")
        table.add_row("Original duration", f"{edl.get('original_duration_seconds', 0):.0f}s")
        table.add_row("Edited duration", f"{edl.get('edited_duration_seconds', 0):.0f}s")
        table.add_row("Time removed", f"{edl.get('time_removed_seconds', 0):.0f}s ({edl.get('time_removed_percent', 0):.1f}%)")
        table.add_row("Total edits", str(len(edl.get("edits", []))))
        console.print(table)

        # Edit breakdown by type
        edits = edl.get("edits", [])
        cuts = [e for e in edits if e.get("type") == "cut"]
        flagged = [e for e in cuts if e.get("review_flag")]
        console.print(f"\n  Cuts: {len(cuts)} ({len(flagged)} flagged for review)")

    if rationale_path.exists():
        with open(rationale_path) as f:
            rationale = json.load(f)
        summary = rationale.get("summary", {})
        breakdown = summary.get("breakdown", {})
        if breakdown:
            console.print("\n[bold]Edit breakdown:[/bold]")
            for category, info in breakdown.items():
                console.print(f"  {category}: {info.get('count', 0)} edits, {info.get('time_removed', 0):.1f}s")

    if summary_path.exists():
        console.print(f"\n[dim]Show notes: {summary_path}[/dim]")

    console.print()
    console.print("[dim]Review artifacts:[/dim]")
    for label, path in [
        ("EDL sidecar", edl_path),
        ("Rationale", rationale_path),
        ("Summary", summary_path),
    ]:
        exists = "✓" if path.exists() else "✗"
        console.print(f"  [{exists}] {label}: {path}")


def _show_mixing_gate(project_root: Path, manifest: Manifest) -> None:
    """Show mixing gate review information."""
    mixed_path = project_root / manifest.files.mixed_audio
    log_path = project_root / manifest.files.mixing_log
    waveform_path = project_root / manifest.files.waveform

    if log_path.exists():
        with open(log_path) as f:
            mix_log = json.load(f)

        table = Table(title="Mix Summary", show_lines=True)
        table.add_column("Metric", style="bold")
        table.add_column("Value")
        table.add_row("Output duration", f"{mix_log.get('output_duration_seconds', 0):.0f}s")
        table.add_row("Sample rate", f"{mix_log.get('output_sample_rate', 0)} Hz")
        table.add_row("Bit depth", f"{mix_log.get('output_bit_depth', 0)}-bit")
        table.add_row("EDL events", str(mix_log.get("edl_events_applied", 0)))
        table.add_row("Crossfades", str(mix_log.get("crossfades_applied", 0)))
        table.add_row("Ducking regions", str(mix_log.get("ducking_regions", 0)))
        console.print(table)

    console.print()
    console.print("[dim]Review artifacts:[/dim]")
    for label, path in [
        ("Mixed audio", mixed_path),
        ("Mixing log", log_path),
        ("Waveform", waveform_path),
    ]:
        exists = "✓" if path.exists() else "✗"
        console.print(f"  [{exists}] {label}: {path}")


def _show_mastering_gate(project_root: Path, manifest: Manifest) -> None:
    """Show mastering gate review information."""
    mp3_path = project_root / manifest.files.mastered_mp3
    wav_path = project_root / manifest.files.mastered_wav
    meta_path = project_root / manifest.files.metadata_json

    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        loudness = meta.get("loudness", {})
        file_info = meta.get("file_info", {})

        table = Table(title="Mastering Summary", show_lines=True)
        table.add_column("Metric", style="bold")
        table.add_column("Value")
        table.add_row("Integrated LUFS", f"{loudness.get('integrated_lufs', '?')}")
        table.add_row("True peak", f"{loudness.get('true_peak_dbtp', '?')} dBTP")
        table.add_row("LRA", f"{loudness.get('loudness_range_lu', '?')} LU")
        table.add_row("MP3 size", f"{file_info.get('mp3_size_bytes', 0) / 1_000_000:.1f} MB")
        table.add_row("Duration", f"{file_info.get('mp3_duration_seconds', 0):.0f}s")
        console.print(table)

    console.print()
    console.print("[dim]Review artifacts:[/dim]")
    for label, path in [
        ("MP3", mp3_path),
        ("WAV", wav_path),
        ("Metadata", meta_path),
    ]:
        exists = "✓" if path.exists() else "✗"
        console.print(f"  [{exists}] {label}: {path}")


def show_gate_status(manifest_path: Path) -> None:
    """Show current gate status."""
    data = read_yaml(manifest_path)
    manifest = Manifest(**data)

    for stage_name in ["ingestion", "editing", "mixing", "mastering"]:
        stage = manifest.get_stage(stage_name)
        if stage.status == "completed" and stage.gate_approved is None:
            console.print(f"[yellow]Gate pending:[/yellow] {stage_name}")
            console.print("Run `podagent gate approve` to continue.")
            return

    console.print("[dim]No gates pending.[/dim]")


def approve_gate(manifest_path: Path, *, notes: str | None = None) -> None:
    """Approve the current pending gate."""
    data = read_yaml(manifest_path)
    manifest = Manifest(**data)

    for stage_name in ["ingestion", "editing", "mixing", "mastering"]:
        stage = manifest.get_stage(stage_name)
        if stage.status == "completed" and stage.gate_approved is None:
            stage.gate_approved = True
            stage.gate_approved_at = datetime.now(timezone.utc)
            if notes:
                stage.gate_notes = notes

            # Advance to next stage
            from podagent.pipeline.orchestrator import _next_stage
            manifest.pipeline.current_stage = _next_stage(stage_name)

            write_yaml(manifest_path, manifest.model_dump(mode="json"))
            log_success(f"Approved gate: {stage_name}")
            return

    raise RuntimeError("No gate pending approval")


def reject_gate(manifest_path: Path, *, notes: str | None = None) -> None:
    """Reject the current pending gate, resetting the stage for re-run."""
    data = read_yaml(manifest_path)
    manifest = Manifest(**data)

    for stage_name in ["ingestion", "editing", "mixing", "mastering"]:
        stage = manifest.get_stage(stage_name)
        if stage.status == "completed" and stage.gate_approved is None:
            stage.status = "pending"
            stage.started_at = None
            stage.completed_at = None
            stage.gate_approved = None
            if notes:
                stage.gate_notes = notes
            manifest.pipeline.current_stage = stage_name

            write_yaml(manifest_path, manifest.model_dump(mode="json"))
            log(f"Gate rejected: {stage_name}. Stage reset to pending.")
            return

    raise RuntimeError("No gate pending review")
