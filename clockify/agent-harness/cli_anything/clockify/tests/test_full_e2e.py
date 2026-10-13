"""Installed CLI smoke tests and explicitly selected real Clockify service tests."""

import json
import os
from datetime import datetime, timedelta, timezone
from importlib.resources import files
from uuid import uuid4

import pytest

from cli_anything.clockify import __version__

from .helpers import offline_env, run_cli


@pytest.mark.parametrize(
    "args",
    [
        ["--help"],
        ["time", "--help"],
        ["project", "--help"],
        ["workspace", "--help"],
        ["client", "--help"],
        ["tag", "--help"],
        ["task", "--help"],
        ["team", "--help"],
        ["report", "--help"],
    ],
)
def test_installed_command_help(args):
    result = run_cli(*args, env=offline_env())
    assert result.returncode == 0, result.stderr
    assert "Usage:" in result.stdout


def test_installed_version_and_bundled_skill():
    result = run_cli("--version", env=offline_env())
    assert result.returncode == 0
    assert __version__ in result.stdout
    package = files("cli_anything.clockify")
    assert "name: cli-anything-clockify" in package.joinpath(
        "skills/SKILL.md"
    ).read_text(encoding="utf-8")
    assert package.joinpath("README.md").is_file()


def test_installed_missing_credentials_is_json():
    result = run_cli("--json", "whoami", env=offline_env())
    assert result.returncode == 1
    assert "CLOCKIFY_API_KEY" in json.loads(result.stdout)["error"]["message"]


def _live_env():
    env = os.environ.copy()
    assert env.get("CLOCKIFY_API_KEY"), "Live tests require CLOCKIFY_API_KEY."
    assert env.get("CLOCKIFY_WORKSPACE_ID"), "Live tests require CLOCKIFY_WORKSPACE_ID."
    return env


def _live_json(*args, env):
    result = run_cli("--json", *args, env=env)
    assert result.returncode == 0, (result.stdout, result.stderr)
    return json.loads(result.stdout)


@pytest.mark.live
def test_live_read_profile_and_workspace():
    env = _live_env()
    user = _live_json("whoami", env=env)
    assert user["id"]
    workspaces = _live_json("workspace", "list", env=env)
    assert any(w["id"] == env["CLOCKIFY_WORKSPACE_ID"] for w in workspaces)
    workspace = _live_json("workspace", "get", env=env)
    assert workspace["id"] == env["CLOCKIFY_WORKSPACE_ID"]


@pytest.mark.live
def test_live_read_projects_and_time_entries():
    env = _live_env()
    projects = _live_json("project", "list", "--page-size", "2", env=env)
    entries = _live_json("time", "list", "--page-size", "2", env=env)
    assert isinstance(projects, list)
    assert isinstance(entries, list)


@pytest.mark.live
def test_live_read_detailed_report():
    env = _live_env()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=1)
    report = _live_json(
        "report",
        "detailed",
        "--start",
        start.isoformat(),
        "--end",
        end.isoformat(),
        "--page-size",
        "2",
        env=env,
    )
    assert isinstance(report, dict)
    assert isinstance(report["timeentries"], list)


@pytest.mark.live
def test_live_write_manual_entry_lifecycle():
    env = _live_env()
    assert env.get("CLOCKIFY_LIVE_WRITES") == "1", (
        "Use a disposable workspace and set CLOCKIFY_LIVE_WRITES=1."
    )
    description = "cli-anything-clockify-test-" + uuid4().hex
    end = datetime.now(timezone.utc) - timedelta(minutes=1)
    start = end - timedelta(minutes=1)
    entry = _live_json(
        "time",
        "create",
        "--start",
        start.isoformat(),
        "--end",
        end.isoformat(),
        "--description",
        description,
        "--non-billable",
        env=env,
    )
    entry_id = entry["id"]
    try:
        saved = _live_json("time", "get", entry_id, env=env)
        assert saved["description"] == description
        assert saved["workspaceId"] == env["CLOCKIFY_WORKSPACE_ID"]
    finally:
        removed = _live_json("time", "delete", entry_id, "--yes", env=env)
        assert removed["deleted"] == entry_id
