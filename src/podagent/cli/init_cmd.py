"""podagent init — scaffold a new episode project."""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from podagent.models.manifest import Files, Manifest, Participant, Pipeline, Project
from podagent.utils.io import write_yaml
from podagent.utils.progress import log, log_success


@click.command()
@click.option("--title", required=True, help="Episode title")
@click.option("--show", default="My Podcast", help="Show/podcast name")
@click.option("--episode", default=1, type=int, help="Episode number")
@click.option("--date", default=None, help="Recording date (YYYY-MM-DD)")
@click.option(
    "--tracks",
    multiple=True,
    required=True,
    type=click.Path(exists=True),
    help="Audio track files (one per speaker)",
)
@click.option(
    "--names",
    multiple=True,
    help="Speaker names (in same order as tracks). Defaults to Speaker_1, Speaker_2...",
)
@click.option(
    "--roles",
    multiple=True,
    help="Speaker roles: host, guest, co-host (in same order as tracks). First defaults to host.",
)
@click.option(
    "--output", "-o",
    default=".",
    type=click.Path(),
    help="Output directory for the project",
)
def init_cmd(
    title: str,
    show: str,
    episode: int,
    date: str | None,
    tracks: tuple[str, ...],
    names: tuple[str, ...],
    roles: tuple[str, ...],
    output: str,
) -> None:
    """Scaffold a new episode project."""
    from datetime import date as date_cls

    project_dir = Path(output).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create directory structure
    tracks_dir = project_dir / "tracks"
    tracks_dir.mkdir(exist_ok=True)
    for subdir in ["ingestion", "editing", "mixing", "mastering"]:
        (project_dir / "artifacts" / subdir).mkdir(parents=True, exist_ok=True)
    (project_dir / "config").mkdir(exist_ok=True)

    # Copy tracks into project
    participants = []
    for i, track_path in enumerate(tracks):
        src = Path(track_path).resolve()
        dst = tracks_dir / src.name
        if src != dst:
            log(f"Copying {src.name} → tracks/")
            shutil.copy2(src, dst)

        name = names[i] if i < len(names) else f"Speaker_{i + 1}"
        role = roles[i] if i < len(roles) else ("host" if i == 0 else "guest")
        participants.append(Participant(
            name=name,
            role=role,
            track=f"tracks/{src.name}",
        ))

    recording_date = date or date_cls.today().isoformat()

    manifest = Manifest(
        project=Project(
            name=show,
            episode_number=episode,
            title=title,
            recording_date=recording_date,
            participants=participants,
        ),
        files=Files(),
        pipeline=Pipeline(),
    )

    manifest_path = project_dir / "manifest.yaml"
    write_yaml(manifest_path, manifest.model_dump(mode="json"))

    log_success(f"Project initialized: {project_dir}")
    log_success(f"Manifest: {manifest_path}")
    log_success(f"Tracks: {len(tracks)} file(s) copied")
    click.echo(f"\nNext: cd {project_dir} && podagent run")
