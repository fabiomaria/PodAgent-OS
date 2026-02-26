"""podagent gate — manage review gates."""

from __future__ import annotations

from pathlib import Path

import click

from podagent.utils.progress import log, log_error, log_success


@click.group(invoke_without_command=True)
@click.option(
    "--manifest", "-m",
    default="manifest.yaml",
    type=click.Path(),
    help="Path to manifest.yaml",
)
@click.pass_context
def gate_cmd(ctx: click.Context, manifest: str) -> None:
    """Manage review gates between pipeline stages."""
    ctx.ensure_object(dict)
    ctx.obj["manifest_path"] = Path(manifest).resolve()

    if ctx.invoked_subcommand is None:
        # Show current gate status
        from podagent.pipeline.gate import show_gate_status
        show_gate_status(ctx.obj["manifest_path"])


@gate_cmd.command("approve")
@click.option("--notes", default=None, help="Approval notes")
@click.pass_context
def approve(ctx: click.Context, notes: str | None) -> None:
    """Approve the current review gate."""
    from podagent.pipeline.gate import approve_gate
    try:
        approve_gate(ctx.obj["manifest_path"], notes=notes)
        log_success("Gate approved")
    except Exception as e:
        log_error(str(e))
        raise SystemExit(1)


@gate_cmd.command("reject")
@click.option("--notes", default=None, help="Rejection notes")
@click.pass_context
def reject(ctx: click.Context, notes: str | None) -> None:
    """Reject the current gate, re-run previous module."""
    from podagent.pipeline.gate import reject_gate
    try:
        reject_gate(ctx.obj["manifest_path"], notes=notes)
        log("Gate rejected. Re-run `podagent run` to retry the stage.")
    except Exception as e:
        log_error(str(e))
        raise SystemExit(1)
