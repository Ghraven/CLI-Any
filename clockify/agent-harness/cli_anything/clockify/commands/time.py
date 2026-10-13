"""Time entry and timer commands."""

from collections.abc import Callable
from typing import Any

import click

from cli_anything.clockify.core.session import Session
from cli_anything.clockify.utils.command import (
    date_range,
    emit,
    json_file,
    now,
    pagination_options,
    pass_session,
    require_yes,
    timestamp,
    timestamp_option,
)


@click.group()
def time() -> None:
    """List and edit time entries, or start and stop timers."""


@time.command("list")
@click.option("--user", "user_id", help="Defaults to the authenticated user.")
@click.option("--start", callback=timestamp_option)
@click.option("--end", callback=timestamp_option)
@click.option("--project", "project_id")
@click.option("--description")
@click.option("--in-progress/--completed", default=None)
@pagination_options
@pass_session
def list_entries(
    session: Session,
    user_id: str | None,
    start: str | None,
    end: str | None,
    project_id: str | None,
    description: str | None,
    in_progress: bool | None,
    **pagination: Any,
) -> None:
    date_range(start, end)
    session.workspace_path()
    user_id = user_id or session.api.current_user_id()
    emit(
        session,
        session.api.list_pages(
            session.workspace_path("user", user_id, "time-entries"),
            params={
                "start": start,
                "end": end,
                "project": project_id,
                "description": description,
                "in-progress": in_progress,
            },
            **pagination,
        ),
    )


@time.command("get")
@click.argument("entry_id")
@pass_session
def get_entry(session: Session, entry_id: str) -> None:
    """Read a single time entry."""
    emit(
        session,
        session.api.request("GET", session.workspace_path("time-entries", entry_id)),
    )


def _entry_options(func: Callable) -> Callable:
    for option in [
        click.option("--description", default=""),
        click.option("--project", "project_id"),
        click.option("--task", "task_id"),
        click.option("--tag", "tag_ids", multiple=True),
        click.option("--billable/--non-billable", default=None),
        click.option(
            "--custom-fields",
            type=click.Path(exists=True, dir_okay=False),
            help="JSON array of customFieldId/value objects.",
        ),
        click.option(
            "--type",
            "entry_type",
            type=click.Choice(["REGULAR", "BREAK"]),
            default="REGULAR",
        ),
    ]:
        func = option(func)
    return func


def _entry_body(
    start: str,
    description: str,
    project_id: str | None,
    task_id: str | None,
    tag_ids: tuple[str, ...],
    billable: bool | None,
    custom_fields: str | None,
    entry_type: str,
) -> dict[str, Any]:
    if len(description) > 3000:
        raise click.BadParameter("description must not exceed 3000 characters")
    if task_id and not project_id:
        raise click.UsageError("--task requires --project.")
    body: dict[str, Any] = {
        "start": start,
        "description": description,
        "type": entry_type,
    }
    for key, value in {
        "projectId": project_id,
        "taskId": task_id,
        "billable": billable,
    }.items():
        if value is not None:
            body[key] = value
    if tag_ids:
        body["tagIds"] = list(tag_ids)
    if custom_fields is not None:
        fields = json_file(custom_fields, list)
        if any(
            not isinstance(field, dict) or not field.get("customFieldId")
            for field in fields
        ):
            raise click.BadParameter("each custom field must have a customFieldId")
        body["customFields"] = fields
    return body


@time.command("create")
@click.option("--start", required=True, callback=timestamp_option)
@click.option("--end", required=True, callback=timestamp_option)
@_entry_options
@pass_session
def create_entry(session: Session, start: str, end: str, **options: Any) -> None:
    """Create a completed time entry."""
    date_range(start, end)
    body = _entry_body(start=start, **options)
    body["end"] = end
    emit(
        session,
        session.api.request("POST", session.workspace_path("time-entries"), body=body),
    )


@time.command("start")
@click.option(
    "--start", callback=timestamp_option, help="Defaults to the current UTC time."
)
@_entry_options
@pass_session
def start_timer(session: Session, start: str | None, **options: Any) -> None:
    """Start a timer for the authenticated user."""
    body = _entry_body(start=start or now(), **options)
    emit(
        session,
        session.api.request("POST", session.workspace_path("time-entries"), body=body),
    )


@time.command("stop")
@click.option(
    "--end", callback=timestamp_option, help="Defaults to the current UTC time."
)
@click.option("--user", "user_id", help="Defaults to the authenticated user.")
@pass_session
def stop_timer(session: Session, end: str | None, user_id: str | None) -> None:
    """Stop a user's current timer in the selected workspace."""
    session.workspace_path()
    user_id = user_id or session.api.current_user_id()
    emit(
        session,
        session.api.request(
            "PATCH",
            session.workspace_path("user", user_id, "time-entries"),
            body={"end": end or now()},
        ),
    )


@time.command("update")
@click.argument("entry_id")
@click.option("--data", required=True, type=click.Path(exists=True, dir_okay=False))
@pass_session
def update_entry(session: Session, entry_id: str, data: str) -> None:
    """Replace an entry using a complete API request JSON file (start required)."""
    body = json_file(data)
    if not isinstance(body.get("start"), str):
        raise click.BadParameter("time entry JSON must contain a start timestamp")
    body["start"] = timestamp(body["start"])
    if body.get("end") is not None:
        if not isinstance(body["end"], str):
            raise click.BadParameter("end must be a timestamp or null")
        body["end"] = timestamp(body["end"])
    date_range(body["start"], body.get("end"))
    emit(
        session,
        session.api.request(
            "PUT", session.workspace_path("time-entries", entry_id), body=body
        ),
    )


@time.command("delete")
@click.argument("entry_id")
@click.option("--yes", is_flag=True, help="Confirm permanent deletion.")
@pass_session
def delete_entry(session: Session, entry_id: str, yes: bool) -> None:
    """Permanently delete one entry."""
    require_yes(yes)
    session.api.request("DELETE", session.workspace_path("time-entries", entry_id))
    emit(session, {"deleted": entry_id})
