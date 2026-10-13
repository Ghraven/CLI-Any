"""Clockify summary and paged detailed reports."""

from collections.abc import Callable
from typing import Any

import click

from cli_anything.clockify.core.session import Session
from cli_anything.clockify.utils.command import (
    date_range,
    emit,
    pass_session,
    timestamp_option,
)


@click.group()
def report() -> None:
    """Query the Reports API using explicit date ranges."""


def _report_options(func: Callable) -> Callable:
    for option in [
        click.option("--start", required=True, callback=timestamp_option),
        click.option("--end", required=True, callback=timestamp_option),
        click.option("--user", "users", multiple=True),
        click.option("--project", "projects", multiple=True),
        click.option("--client", "clients", multiple=True),
        click.option("--tag", "tags", multiple=True),
        click.option("--billable/--non-billable", default=None),
        click.option("--description"),
    ]:
        func = option(func)
    return func


def _body(
    start: str,
    end: str,
    users: tuple[str, ...],
    projects: tuple[str, ...],
    clients: tuple[str, ...],
    tags: tuple[str, ...],
    billable: bool | None,
    description: str | None,
) -> dict[str, Any]:
    date_range(start, end)
    # Reports interprets offset-free timestamps in timeZone, unlike the core API.
    body: dict[str, Any] = {
        "dateRangeStart": start.removesuffix("Z"),
        "dateRangeEnd": end.removesuffix("Z"),
        "dateRangeType": "ABSOLUTE",
        "timeZone": "UTC",
        "exportType": "JSON",
    }
    for key, ids in {
        "users": users,
        "projects": projects,
        "clients": clients,
        "tags": tags,
    }.items():
        if ids:
            body[key] = {"ids": list(ids), "contains": "CONTAINS"}
    if billable is not None:
        body["billable"] = billable
    if description is not None:
        body["description"] = description
    return body


@report.command("summary")
@_report_options
@click.option(
    "--group",
    "groups",
    multiple=True,
    help="Grouping dimension, e.g. USER or PROJECT. Defaults to PROJECT.",
)
@pass_session
def summary(session: Session, groups: tuple[str, ...], **options: Any) -> None:
    """Summarize time by the requested grouping dimensions."""
    body = _body(**options)
    body["summaryFilter"] = {"groups": list(groups or ("PROJECT",))}
    emit(
        session,
        session.api.request(
            "POST",
            session.workspace_path("reports", "summary"),
            body=body,
            reports=True,
        ),
    )


@report.command("detailed")
@_report_options
@click.option("--page", type=click.IntRange(min=1), default=1, show_default=True)
@click.option(
    "--page-size", type=click.IntRange(1, 1000), default=50, show_default=True
)
@pass_session
def detailed(session: Session, page: int, page_size: int, **options: Any) -> None:
    """Return one report page, including its server-provided totals."""
    body = _body(**options)
    body["detailedFilter"] = {"page": page, "pageSize": page_size}
    emit(
        session,
        session.api.request(
            "POST",
            session.workspace_path("reports", "detailed"),
            body=body,
            reports=True,
        ),
    )
