"""podagent run — run the processing pipeline."""

from __future__ import annotations

from pathlib import Path

import click

from podagent.utils.progress import log_error


@click.command()
@click.option(
    "--manifest", "-m",
    default="manifest.yaml",
    type=click.Path(),
    help="Path to manifest.yaml",
)
@click.option(
    "--from", "from_stage",
    default=None,
    type=click.Choice(["ingestion", "editing", "mixing", "mastering"]),
    help="Resume from a specific stage",
)
def run_cmd(manifest: str, from_stage: str | None) -> None:
    """Run the podcast production pipeline."""
    manifest_path = Path(manifest).resolve()
    if not manifest_path.exists():
        log_error(f"Manifest not found: {manifest_path}")
        raise SystemExit(1)

    from podagent.pipeline.orchestrator import run_pipeline

    try:
        run_pipeline(manifest_path, from_stage=from_stage)
    except Exception as e:
        log_error(f"Pipeline failed: {e}")
        raise SystemExit(1)
