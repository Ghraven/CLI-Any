"""Workspace, project, client, tag, task and team commands."""

from typing import Any

import click

from cli_anything.clockify.core.api import path
from cli_anything.clockify.core.session import Session
from cli_anything.clockify.utils.command import (
    emit,
    json_file,
    pagination_options,
    pass_session,
    require_yes,
    validate_name,
)


@click.group()
def workspace() -> None:
    """Discover workspaces and select the current REPL workspace."""


@workspace.command("list")
@pass_session
def list_workspaces(session: Session) -> None:
    """List all workspaces accessible to the authenticated user."""
    emit(session, session.api.request("GET", "workspaces"))


@workspace.command("get")
@pass_session
def get_workspace(session: Session) -> None:
    """Read the selected workspace."""
    emit(session, session.api.request("GET", session.workspace_path()))


@workspace.command("users")
@click.option("--name")
@click.option("--email")
@pagination_options
@pass_session
def workspace_users(
    session: Session, name: str | None, email: str | None, **pagination: Any
) -> None:
    """List workspace members."""
    emit(
        session,
        session.api.list_pages(
            session.workspace_path("users"),
            params={"name": name, "email": email, "include-roles": False},
            **pagination,
        ),
    )


@workspace.command("use")
@click.argument("workspace_id")
@pass_session
def use_workspace(session: Session, workspace_id: str) -> None:
    """Select a workspace for this REPL session; no configuration file is written."""
    path("workspaces", workspace_id)
    session.workspace_id = workspace_id
    emit(session, {"workspace_id": workspace_id})


@workspace.command("current")
@pass_session
def current_workspace(session: Session) -> None:
    """Show the current workspace selection without contacting Clockify."""
    emit(session, {"workspace_id": session.workspace_id})


@click.group()
def project() -> None:
    """Manage projects in the selected workspace."""


@project.command("list")
@click.option("--name")
@click.option("--archived/--active", default=None)
@pagination_options
@pass_session
def list_projects(
    session: Session, name: str | None, archived: bool | None, **pagination: Any
) -> None:
    emit(
        session,
        session.api.list_pages(
            session.workspace_path("projects"),
            params={"name": name, "archived": archived},
            **pagination,
        ),
    )


@project.command("get")
@click.argument("project_id")
@pass_session
def get_project(session: Session, project_id: str) -> None:
    emit(
        session,
        session.api.request("GET", session.workspace_path("projects", project_id)),
    )


@project.command("create")
@click.argument("name")
@click.option("--client", "client_id")
@click.option("--public/--private", "is_public", default=False)
@click.option("--billable/--non-billable", default=False)
@click.option("--color", default="#03A9F4", show_default=True)
@click.option("--note", default="")
@pass_session
def create_project(
    session: Session,
    name: str,
    client_id: str | None,
    is_public: bool,
    billable: bool,
    color: str,
    note: str,
) -> None:
    if (
        len(color) != 7
        or color[0] != "#"
        or any(c not in "0123456789abcdefABCDEF" for c in color[1:])
    ):
        raise click.BadParameter("--color must be a six-digit RGB hex color")
    body = {
        "name": validate_name(name, 2),
        "isPublic": is_public,
        "billable": billable,
        "color": color,
        "note": note,
    }
    if client_id is not None:
        body["clientId"] = client_id
    emit(
        session,
        session.api.request("POST", session.workspace_path("projects"), body=body),
    )


@project.command("update")
@click.argument("project_id")
@click.option("--data", required=True, type=click.Path(exists=True, dir_okay=False))
@pass_session
def update_project(session: Session, project_id: str, data: str) -> None:
    """Send a complete project update request from a JSON file."""
    emit(
        session,
        session.api.request(
            "PUT",
            session.workspace_path("projects", project_id),
            body=json_file(data),
        ),
    )


@project.command("delete")
@click.argument("project_id")
@click.option("--yes", is_flag=True)
@pass_session
def delete_project(session: Session, project_id: str, yes: bool) -> None:
    """Delete a project; Clockify may require archiving it first."""
    require_yes(yes)
    session.api.request("DELETE", session.workspace_path("projects", project_id))
    emit(session, {"deleted": project_id})


def _named_resource(
    name: str, resource: str, maximum: int, *, can_get: bool = True
) -> click.Group:
    """Register the common name-based resource operations."""
    group = click.Group(name=name, help=f"Manage {name}s in the selected workspace.")

    @group.command("list")
    @click.option("--name")
    @pagination_options
    @pass_session
    def list_items(session: Session, name: str | None, **pagination: Any) -> None:
        emit(
            session,
            session.api.list_pages(
                session.workspace_path(resource),
                params={"name": name},
                **pagination,
            ),
        )

    @group.command("create")
    @click.argument("name")
    @pass_session
    def create_item(session: Session, name: str) -> None:
        emit(
            session,
            session.api.request(
                "POST",
                session.workspace_path(resource),
                body={"name": validate_name(name, maximum=maximum)},
            ),
        )

    @group.command("update")
    @click.argument("resource_id")
    @click.option("--data", required=True, type=click.Path(exists=True, dir_okay=False))
    @pass_session
    def update_item(session: Session, resource_id: str, data: str) -> None:
        """Send a complete API update request from a JSON file."""
        emit(
            session,
            session.api.request(
                "PUT",
                session.workspace_path(resource, resource_id),
                body=json_file(data),
            ),
        )

    @group.command("delete")
    @click.argument("resource_id")
    @click.option("--yes", is_flag=True)
    @pass_session
    def delete_item(session: Session, resource_id: str, yes: bool) -> None:
        require_yes(yes)
        session.api.request("DELETE", session.workspace_path(resource, resource_id))
        emit(session, {"deleted": resource_id})

    if can_get:

        @group.command("get")
        @click.argument("resource_id")
        @pass_session
        def get_item(session: Session, resource_id: str) -> None:
            emit(
                session,
                session.api.request(
                    "GET", session.workspace_path(resource, resource_id)
                ),
            )

    return group


client = _named_resource("client", "clients", 100)
tag = _named_resource("tag", "tags", 100)
team = _named_resource("team", "user-groups", 100, can_get=False)


@team.command("add-member")
@click.argument("team_id")
@click.argument("user_id")
@pass_session
def add_member(session: Session, team_id: str, user_id: str) -> None:
    """Add a workspace user to a user group."""
    emit(
        session,
        session.api.request(
            "POST",
            session.workspace_path("user-groups", team_id, "users"),
            body={"userId": user_id},
        ),
    )


@team.command("remove-member")
@click.argument("team_id")
@click.argument("user_id")
@click.option("--yes", is_flag=True)
@pass_session
def remove_member(session: Session, team_id: str, user_id: str, yes: bool) -> None:
    require_yes(yes)
    session.api.request(
        "DELETE", session.workspace_path("user-groups", team_id, "users", user_id)
    )
    emit(session, {"team_id": team_id, "removed": user_id})


@click.group()
def task() -> None:
    """Manage project tasks."""


@task.command("list")
@click.argument("project_id")
@click.option("--name")
@click.option("--active/--done", default=None)
@pagination_options
@pass_session
def list_tasks(
    session: Session,
    project_id: str,
    name: str | None,
    active: bool | None,
    **pagination: Any,
) -> None:
    emit(
        session,
        session.api.list_pages(
            session.workspace_path("projects", project_id, "tasks"),
            params={"name": name, "is-active": active},
            **pagination,
        ),
    )


@task.command("get")
@click.argument("project_id")
@click.argument("task_id")
@pass_session
def get_task(session: Session, project_id: str, task_id: str) -> None:
    emit(
        session,
        session.api.request(
            "GET", session.workspace_path("projects", project_id, "tasks", task_id)
        ),
    )


@task.command("create")
@click.argument("project_id")
@click.argument("name")
@click.option("--assignee", "assignees", multiple=True)
@pass_session
def create_task(
    session: Session, project_id: str, name: str, assignees: tuple[str, ...]
) -> None:
    body: dict[str, Any] = {"name": validate_name(name, maximum=1000)}
    if assignees:
        body["assigneeIds"] = list(assignees)
    emit(
        session,
        session.api.request(
            "POST", session.workspace_path("projects", project_id, "tasks"), body=body
        ),
    )


@task.command("update")
@click.argument("project_id")
@click.argument("task_id")
@click.option("--data", required=True, type=click.Path(exists=True, dir_okay=False))
@pass_session
def update_task(session: Session, project_id: str, task_id: str, data: str) -> None:
    """Send a complete task update request from a JSON file."""
    emit(
        session,
        session.api.request(
            "PUT",
            session.workspace_path("projects", project_id, "tasks", task_id),
            body=json_file(data),
        ),
    )


@task.command("delete")
@click.argument("project_id")
@click.argument("task_id")
@click.option("--yes", is_flag=True)
@pass_session
def delete_task(session: Session, project_id: str, task_id: str, yes: bool) -> None:
    require_yes(yes)
    session.api.request(
        "DELETE", session.workspace_path("projects", project_id, "tasks", task_id)
    )
    emit(session, {"deleted": task_id})
