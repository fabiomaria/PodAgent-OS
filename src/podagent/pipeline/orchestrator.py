"""Sequential pipeline runner with resume logic."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from podagent.models.manifest import Manifest, StageError
from podagent.utils.io import read_yaml, write_yaml
from podagent.utils.progress import log, log_error, log_step, log_success, log_warning


STAGE_ORDER = ["ingestion", "editing", "mixing", "mastering"]


class ModuleInterface(Protocol):
    """Protocol that all pipeline modules must implement."""

    name: str

    def run(self, project_root: Path, manifest: Manifest) -> None: ...
    def validate_inputs(self, project_root: Path, manifest: Manifest) -> list[str]: ...


def _load_module(stage_name: str) -> ModuleInterface:
    """Dynamically load a pipeline module."""
    if stage_name == "ingestion":
        from podagent.ingestion.module import IngestionModule
        return IngestionModule()
    elif stage_name == "editing":
        from podagent.editing.module import EditingModule
        return EditingModule()
    elif stage_name == "mixing":
        from podagent.mixing.module import MixingModule
        return MixingModule()
    elif stage_name == "mastering":
        from podagent.mastering.module import MasteringModule
        return MasteringModule()
    else:
        raise ValueError(f"Unknown stage: {stage_name}")


def _load_manifest(manifest_path: Path) -> Manifest:
    """Load and validate the manifest."""
    data = read_yaml(manifest_path)
    return Manifest(**data)


def _save_manifest(manifest_path: Path, manifest: Manifest) -> None:
    """Save the manifest atomically."""
    write_yaml(manifest_path, manifest.model_dump(mode="json"))


def run_pipeline(manifest_path: Path, *, from_stage: str | None = None) -> None:
    """Run the pipeline from the current (or specified) stage.

    Resume logic:
    1. Read manifest.pipeline.stages
    2. For each stage [ingestion, editing, mixing, mastering]:
       - completed + gate_approved → skip
       - completed + gate_approved=null → present gate
       - failed/in_progress → re-run
       - pending → run
    """
    manifest = _load_manifest(manifest_path)
    project_root = manifest_path.parent

    log(f"[bold]PodAgent OS[/bold] — {manifest.project.title}")
    log(f"Project: {project_root}")

    # Determine starting stage
    start_idx = 0
    if from_stage:
        if from_stage not in STAGE_ORDER:
            raise ValueError(f"Unknown stage: {from_stage}")
        start_idx = STAGE_ORDER.index(from_stage)
        log(f"Resuming from: [cyan]{from_stage}[/cyan]")

    for stage_name in STAGE_ORDER[start_idx:]:
        stage = manifest.get_stage(stage_name)

        # Skip completed + approved stages
        if stage.status == "completed" and stage.gate_approved is True:
            log(f"[dim]Skipping {stage_name} (completed + approved)[/dim]")
            continue

        # Present gate for completed but unapproved stages
        if stage.status == "completed" and stage.gate_approved is None:
            from podagent.pipeline.gate import present_gate

            log_step(stage_name, "Awaiting gate review")
            approved = present_gate(project_root, manifest, stage_name)
            if approved:
                stage.gate_approved = True
                stage.gate_approved_at = datetime.now(timezone.utc)
                manifest.pipeline.current_stage = _next_stage(stage_name)
                _save_manifest(manifest_path, manifest)
                log_success(f"Gate approved for {stage_name}")
                continue
            else:
                log_warning(f"Gate not approved for {stage_name}. Pipeline paused.")
                _save_manifest(manifest_path, manifest)
                return

        # Run the stage
        module = _load_module(stage_name)

        # Validate inputs
        errors = module.validate_inputs(project_root, manifest)
        if errors:
            log_error(f"Cannot run {stage_name}:")
            for err in errors:
                log_error(f"  - {err}")
            raise RuntimeError(f"Input validation failed for {stage_name}")

        # Mark as in_progress
        stage.status = "in_progress"
        stage.started_at = datetime.now(timezone.utc)
        stage.error = None
        manifest.pipeline.current_stage = stage_name
        _save_manifest(manifest_path, manifest)

        log_step(stage_name, "Starting...")

        try:
            module.run(project_root, manifest)
        except Exception as e:
            stage.status = "failed"
            stage.error = StageError(
                type=type(e).__name__,
                message=str(e)[:500],
                step=stage.last_completed_step,
            )
            _save_manifest(manifest_path, manifest)
            log_error(f"{stage_name} failed: {e}")
            raise

        # Mark completed
        stage.status = "completed"
        stage.completed_at = datetime.now(timezone.utc)
        _save_manifest(manifest_path, manifest)

        elapsed = (stage.completed_at - stage.started_at).total_seconds()
        log_success(f"{stage_name} completed in {elapsed:.0f}s")

        # Present gate
        from podagent.pipeline.gate import present_gate

        approved = present_gate(project_root, manifest, stage_name)
        if approved:
            stage.gate_approved = True
            stage.gate_approved_at = datetime.now(timezone.utc)
            manifest.pipeline.current_stage = _next_stage(stage_name)
            _save_manifest(manifest_path, manifest)
        else:
            log_warning(f"Gate not approved. Run `podagent gate approve` when ready.")
            _save_manifest(manifest_path, manifest)
            return

    log_success("[bold]Pipeline complete![/bold]")


def _next_stage(current: str) -> str:
    """Get the next stage name, or 'complete'."""
    idx = STAGE_ORDER.index(current)
    if idx + 1 < len(STAGE_ORDER):
        return STAGE_ORDER[idx + 1]
    return "complete"
