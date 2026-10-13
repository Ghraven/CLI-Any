"""Clockify command line and interactive entry points."""

from __future__ import annotations

import json
import math
import os
import shlex
import sys
from typing import Any

import click

from cli_anything.clockify import __version__
from cli_anything.clockify.commands.report import report
from cli_anything.clockify.commands.resources import (
    client,
    project,
    tag,
    task,
    team,
    workspace,
)
from cli_anything.clockify.commands.time import time
from cli_anything.clockify.core.api import ClockifyAPI, ClockifyError
from cli_anything.clockify.core.session import Session
from cli_anything.clockify.utils.command import emit, pass_session
from cli_anything.clockify.utils.repl_skin import ReplSkin


class ClockifyGroup(click.Group):
    """Keep API and command-validation failures machine-readable in JSON mode."""

    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except (ClockifyError, click.ClickException) as exc:
            json_output = (
                ctx.obj.json_output
                if isinstance(ctx.obj, Session)
                else bool(ctx.params.get("json_output"))
            )
            if json_output:
                error = (
                    exc.as_dict()
                    if isinstance(exc, ClockifyError)
                    else {"message": exc.format_message()}
                )
                click.echo(json.dumps({"error": error}, ensure_ascii=False))
                ctx.exit(exc.exit_code if isinstance(exc, click.ClickException) else 1)
            if isinstance(exc, ClockifyError):
                raise click.ClickException(str(exc)) from None
            raise


@click.group(cls=ClockifyGroup, invoke_without_command=True)
@click.option(
    "--json/--human",
    "json_output",
    default=None,
    help="Compact JSON or formatted output.",
)
@click.option(
    "--workspace",
    "workspace_id",
    help="Workspace ID; defaults to CLOCKIFY_WORKSPACE_ID.",
)
@click.option(
    "--timeout",
    type=click.FloatRange(min=0, min_open=True),
    default=None,
    help="HTTP timeout in seconds (default: 30).",
)
@click.version_option(__version__, prog_name="cli-anything-clockify")
@click.pass_context
def cli(
    ctx: click.Context,
    json_output: bool | None,
    workspace_id: str | None,
    timeout: float | None,
) -> None:
    """Track time, manage projects and teams, and query Clockify reports.

    Set CLOCKIFY_API_KEY before making requests. Run without a command for
    the interactive REPL. All global options precede the command group.
    """
    if timeout is not None and not math.isfinite(timeout):
        raise click.BadParameter("timeout must be finite", param_hint="--timeout")
    if not isinstance(ctx.obj, Session):
        api = ClockifyAPI(timeout=timeout or 30.0)
        ctx.obj = Session(
            api,
            workspace_id or os.environ.get("CLOCKIFY_WORKSPACE_ID"),
            bool(json_output),
        )
        ctx.call_on_close(api.close)
    else:
        if json_output is not None:
            ctx.obj.json_output = json_output
        if workspace_id is not None:
            ctx.obj.workspace_id = workspace_id
        if timeout is not None:
            ctx.obj.api.timeout = timeout
    if ctx.invoked_subcommand is None:
        _start_repl(ctx.obj)


for group in (workspace, project, client, tag, task, team, time, report):
    cli.add_command(group)


@cli.command("whoami")
@pass_session
def whoami(session: Session) -> None:
    """Read the authenticated user's profile."""
    emit(session, session.api.request("GET", "user"))


@cli.command("repl")
@pass_session
def repl(session: Session) -> None:
    """Start an interactive session with a persistent workspace selection."""
    _start_repl(session)


def _start_repl(session: Session) -> None:
    if session.in_repl:
        raise click.UsageError("Already in the REPL.")
    session.in_repl = True
    try:
        _repl_loop(session)
    finally:
        session.in_repl = False


def _repl_loop(session: Session) -> None:
    interactive = sys.stdin.isatty() and not session.json_output
    skin = ReplSkin("clockify", version=__version__) if interactive else None
    prompt = None
    if skin is not None:
        skin.print_banner()
        prompt = skin.create_prompt_session()
    while True:
        try:
            line = (
                skin.get_input(prompt, project_name=session.workspace_id or "")
                if skin
                else input()
            )
        except (EOFError, KeyboardInterrupt):
            break
        if not line.strip():
            continue
        if line.strip() in {"exit", "quit", "q"}:
            break
        try:
            args = ["--help"] if line.strip() in {"help", "?"} else shlex.split(line)
            if args == ["repl"]:
                raise click.UsageError("Already in the REPL.")
            cli.main(args=args, obj=session, standalone_mode=False)
        except (ValueError, click.ClickException) as exc:
            if session.json_output:
                emit(session, {"error": {"message": str(exc)}})
            elif skin:
                skin.error(str(exc))
            else:
                click.echo(f"Error: {exc}", err=True)
        except click.Abort:
            continue
    if skin:
        skin.print_goodbye()


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
