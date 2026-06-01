"""Typer CLI commands for running the pipeline and serving."""

from __future__ import annotations

import logging
import subprocess
import sys

import typer
from rich.console import Console

app = typer.Typer(
    name="daily-scheduler",
    help=("AI-powered daily news & trading report system"),
)
console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Configure logging level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format=("%(asctime)s [%(levelname)s] %(name)s: %(message)s"),
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@app.command()
def run(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    ),
) -> None:
    """Run the daily report pipeline."""
    setup_logging(verbose)
    from daily_scheduler.database import (
        get_session_factory,
    )
    from daily_scheduler.infrastructure.dependencies import (
        get_daily_pipeline,
    )

    console.print("[bold blue]Starting daily report pipeline...[/bold blue]")
    session_factory = get_session_factory()
    session = session_factory()
    try:
        pipeline = get_daily_pipeline(session)
        success = pipeline.execute()
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    if success:
        console.print("[bold green]Pipeline completed successfully![/bold green]")
    else:
        console.print("[bold red]Pipeline failed. Check logs for details.[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def serve(
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        "-h",
    ),
    port: int = typer.Option(8000, "--port", "-p"),
    reload: bool = typer.Option(
        False,
        "--reload",
        "-r",
    ),
) -> None:
    """Start the FastAPI dashboard server."""
    import uvicorn

    console.print(f"[bold blue]Starting dashboard at http://{host}:{port}[/bold blue]")
    uvicorn.run(
        "daily_scheduler.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command(name="init-db")
def init_db() -> None:
    """Initialize the database (run Alembic migrations)."""
    from pathlib import Path

    from daily_scheduler.config import get_settings

    settings = get_settings()
    db_path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    alembic_dir = Path(__file__).parent.parent.parent.parent.parent / "alembic.ini"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "upgrade",
            "head",
        ],
        cwd=str(alembic_dir.parent),
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0:
        console.print(f"[bold green]Database initialized at {db_path}[/bold green]")
    else:
        console.print(f"[bold red]Migration failed: {result.stderr}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def check() -> None:
    """Verify configuration and dependencies."""
    from daily_scheduler.config import get_settings

    settings = get_settings()
    all_ok = True

    # Check Claude CLI
    try:
        result = subprocess.run(
            [settings.claude_cli_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0:
            console.print(f"[green]Claude CLI:[/green] {result.stdout.strip()}")
        else:
            console.print(f"[red]Claude CLI:[/red] Error (exit {result.returncode})")
            all_ok = False
    except FileNotFoundError:
        console.print(f"[red]Claude CLI:[/red] Not found at '{settings.claude_cli_path}'")
        all_ok = False

    # Check SMTP
    if settings.smtp_user and settings.smtp_password.get_secret_value():
        console.print(f"[green]SMTP:[/green] Configured ({settings.smtp_user})")
    else:
        console.print("[yellow]SMTP:[/yellow] Not configured (set SMTP_USER and SMTP_PASSWORD)")
        all_ok = False

    # Check email recipients
    if settings.email_to:
        console.print(f"[green]Recipients:[/green] {', '.join(settings.email_to)}")
    else:
        console.print("[yellow]Recipients:[/yellow] Not configured (set EMAIL_TO)")
        all_ok = False

    # Check database
    db_path = settings.db_path
    if db_path.exists():
        console.print(f"[green]Database:[/green] {db_path}")
    else:
        console.print(
            f"[yellow]Database:[/yellow] Not found at {db_path}. Run 'daily-scheduler init-db'"
        )
        all_ok = False

    if all_ok:
        console.print("\n[bold green]All checks passed![/bold green]")
    else:
        console.print("\n[bold yellow]Some checks need attention. See above.[/bold yellow]")
