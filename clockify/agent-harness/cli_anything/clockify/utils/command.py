"""Shared command options and input validation."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from cli_anything.clockify.core.session import Session

pass_session = click.make_pass_decorator(Session)


def emit(session: Session, value: Any) -> None:
    click.echo(
        json.dumps(value, ensure_ascii=False, indent=None if session.json_output else 2)
    )


def timestamp(value: str) -> str:
    """Normalize a timezone-qualified ISO timestamp to UTC."""
    try:
        if "T" not in value:
            raise ValueError
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
    except (TypeError, ValueError):
        raise click.BadParameter(
            "use an ISO timestamp with a timezone, such as 2026-01-01T09:00:00Z"
        ) from None
    return (
        parsed.astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def timestamp_option(
    ctx: click.Context, param: click.Parameter, value: str | None
) -> str | None:
    if value is None:
        return None
    try:
        return timestamp(value)
    except click.BadParameter as exc:
        exc.param = param
        raise


def now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def date_range(start: str | None, end: str | None) -> None:
    if start is not None and end is not None and start > end:
        raise click.BadParameter("--end must not precede --start")


def json_file(filename: str, expected: type = dict) -> Any:
    try:
        value = json.loads(Path(filename).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise click.BadParameter(f"cannot read valid JSON from {filename}") from None
    if not isinstance(value, expected):
        raise click.BadParameter(f"{filename} must contain a JSON {expected.__name__}")
    return value


def validate_name(name: str, minimum: int = 1, maximum: int = 250) -> str:
    if not name.strip() or not minimum <= len(name) <= maximum:
        raise click.BadParameter(f"name must contain {minimum} to {maximum} characters")
    return name


def require_yes(yes: bool) -> None:
    if not yes:
        raise click.UsageError("This deletion requires --yes.")


def pagination_options(func: Callable) -> Callable:
    for option in [
        click.option(
            "--page", type=click.IntRange(min=1), default=1, show_default=True
        ),
        click.option(
            "--page-size", type=click.IntRange(1, 1000), default=50, show_default=True
        ),
        click.option("--all", "all_pages", is_flag=True, help="Collect all pages."),
        click.option(
            "--max-pages", type=click.IntRange(min=1), default=1000, show_default=True
        ),
    ]:
        func = option(func)
    return func
