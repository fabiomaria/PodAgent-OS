"""Root CLI group for PodAgent OS."""

from __future__ import annotations

import click

from podagent import __version__


@click.group()
@click.version_option(version=__version__, prog_name="podagent")
def cli() -> None:
    """PodAgent OS — AI-powered podcast production pipeline."""


# Import and register subcommands
from podagent.cli.init_cmd import init_cmd  # noqa: E402
from podagent.cli.run_cmd import run_cmd  # noqa: E402
from podagent.cli.gate_cmd import gate_cmd  # noqa: E402
from podagent.cli.status_cmd import status_cmd  # noqa: E402

cli.add_command(init_cmd, "init")
cli.add_command(run_cmd, "run")
cli.add_command(gate_cmd, "gate")
cli.add_command(status_cmd, "status")
