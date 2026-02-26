"""Progress reporting utilities using Rich."""

from __future__ import annotations

from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console(stderr=True)


def log(message: str, *, style: str = "bold") -> None:
    """Log a timestamped message."""
    ts = datetime.now().strftime("%H:%M:%S")
    console.print(f"[dim]\\[{ts}][/dim] {message}", style=style, highlight=False)


def log_step(step: str, message: str) -> None:
    """Log a processing step."""
    ts = datetime.now().strftime("%H:%M:%S")
    console.print(
        f"[dim]\\[{ts}][/dim] [bold cyan]{step}[/bold cyan] {message}",
        highlight=False,
    )


def log_success(message: str) -> None:
    """Log a success message."""
    log(f"[green]✓[/green] {message}", style="")


def log_warning(message: str) -> None:
    """Log a warning message."""
    log(f"[yellow]⚠[/yellow] {message}", style="")


def log_error(message: str) -> None:
    """Log an error message."""
    log(f"[red]✗[/red] {message}", style="")


def show_stage_summary(stage: str, duration_seconds: float, details: dict) -> None:
    """Show a summary panel for a completed stage."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()

    for key, value in details.items():
        table.add_row(key, str(value))

    mins = int(duration_seconds) // 60
    secs = int(duration_seconds) % 60
    table.add_row("Duration", f"{mins}m{secs:02d}s")

    console.print(Panel(table, title=f"[bold]{stage} Complete[/bold]", border_style="green"))
