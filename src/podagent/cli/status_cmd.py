"""podagent status — show pipeline state."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from podagent.models.manifest import Manifest
from podagent.utils.io import read_yaml
from podagent.utils.progress import log_error

console = Console()

STAGE_ICONS = {
    "pending": "[dim]○[/dim]",
    "in_progress": "[yellow]◑[/yellow]",
    "completed": "[green]●[/green]",
    "failed": "[red]✗[/red]",
}

GATE_ICONS = {
    True: "[green]✓[/green]",
    False: "[red]✗[/red]",
    None: "[dim]—[/dim]",
}


@click.command()
@click.option(
    "--manifest", "-m",
    default="manifest.yaml",
    type=click.Path(),
    help="Path to manifest.yaml",
)
def status_cmd(manifest: str) -> None:
    """Show pipeline status for the current project."""
    manifest_path = Path(manifest).resolve()
    if not manifest_path.exists():
        log_error(f"Manifest not found: {manifest_path}")
        raise SystemExit(1)

    data = read_yaml(manifest_path)
    m = Manifest(**data)

    # Project info
    console.print(f"\n[bold]{m.project.name}[/bold] — Episode {m.project.episode_number}")
    console.print(f"[dim]{m.project.title}[/dim]")
    console.print(f"Tracks: {len(m.project.participants)} participant(s)")
    console.print()

    # Stage table
    table = Table(title="Pipeline Status", show_lines=True)
    table.add_column("Stage", style="bold")
    table.add_column("Status")
    table.add_column("Gate")
    table.add_column("Started")
    table.add_column("Completed")
    table.add_column("Notes")

    for stage_name in ["ingestion", "editing", "mixing", "mastering"]:
        stage = m.get_stage(stage_name)
        icon = STAGE_ICONS.get(stage.status, "?")
        gate_icon = GATE_ICONS.get(stage.gate_approved)
        started = stage.started_at.strftime("%H:%M:%S") if stage.started_at else "—"
        completed = stage.completed_at.strftime("%H:%M:%S") if stage.completed_at else "—"
        notes = ""
        if stage.error:
            notes = f"[red]{stage.error.message}[/red]"
        elif stage.gate_notes:
            notes = stage.gate_notes[:50]

        current = " ←" if m.pipeline.current_stage == stage_name else ""
        table.add_row(
            f"{stage_name}{current}",
            f"{icon} {stage.status}",
            gate_icon,
            started,
            completed,
            notes,
        )

    console.print(table)
    console.print()
