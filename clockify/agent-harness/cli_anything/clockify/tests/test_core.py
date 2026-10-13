"""Offline tests of CLI behavior and the documented Clockify request contracts."""

import json
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
import responses
from click.testing import CliRunner

from cli_anything.clockify.clockify_cli import cli
from cli_anything.clockify.core.api import (
    CORE_URL,
    REPORTS_URL,
    ClockifyAPI,
    ClockifyError,
    path,
)
from cli_anything.clockify.utils.command import timestamp

KEY = "clockify-test-key"
WS = CORE_URL + "/workspaces/ws"


@pytest.fixture
def runner(monkeypatch):
    for key in (
        "CLOCKIFY_API_URL",
        "CLOCKIFY_REPORTS_URL",
        "CLOCKIFY_WORKSPACE_ID",
        "CLOCKIFY_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CLOCKIFY_API_KEY", KEY)
    monkeypatch.setenv("CLOCKIFY_WORKSPACE_ID", "ws")
    return CliRunner()


@pytest.fixture
def http():
    with responses.RequestsMock(assert_all_requests_are_fired=True) as mock:
        yield mock


def invoke(runner, *args, **kwargs):
    return runner.invoke(cli, ["--json", *args], **kwargs)


def success(result):
    assert result.exit_code == 0, (result.output, result.exception)
    return json.loads(result.stdout)


def failure(result, message):
    assert result.exit_code != 0
    error = json.loads(result.stdout)["error"]
    assert message.lower() in error["message"].lower()
    assert "Traceback" not in result.output
    return error


@pytest.mark.parametrize(
    "args,endpoint,payload",
    [
        (["whoami"], CORE_URL + "/user", {"id": "me"}),
        (["workspace", "list"], CORE_URL + "/workspaces", [{"id": "ws"}]),
        (["workspace", "get"], WS, {"id": "ws"}),
        (["project", "get", "p"], WS + "/projects/p", {"id": "p"}),
        (["client", "get", "c"], WS + "/clients/c", {"id": "c"}),
        (["tag", "get", "t"], WS + "/tags/t", {"id": "t"}),
        (["task", "get", "p", "t"], WS + "/projects/p/tasks/t", {"id": "t"}),
        (["time", "get", "entry"], WS + "/time-entries/entry", {"id": "entry"}),
    ],
)
def test_read_commands(runner, http, args, endpoint, payload):
    http.get(endpoint, json=payload)
    assert success(invoke(runner, *args)) == payload
    assert http.calls[0].request.headers["X-Api-Key"] == KEY


@pytest.mark.parametrize(
    "args,resource",
    [
        (["project", "list"], "projects"),
        (["client", "list"], "clients"),
        (["tag", "list"], "tags"),
        (["team", "list"], "user-groups"),
        (["task", "list", "p"], "projects/p/tasks"),
        (["workspace", "users"], "users"),
    ],
)
def test_resource_lists_have_explicit_pagination(runner, http, args, resource):
    http.get(WS + "/" + resource, json=[{"id": "item"}])
    assert success(invoke(runner, *args, "--page", "2", "--page-size", "10")) == [
        {"id": "item"}
    ]
    query = parse_qs(urlsplit(http.calls[0].request.url).query)
    assert query["page"] == ["2"]
    assert query["page-size"] == ["10"]


def test_list_filters_use_api_field_names(runner, http):
    http.get(WS + "/projects/p/tasks", json=[])
    success(invoke(runner, "task", "list", "p", "--done", "--name", "Fix"))
    query = parse_qs(urlsplit(http.calls[0].request.url).query)
    assert query["is-active"] == ["false"]
    assert query["name"] == ["Fix"]
    http.get(WS + "/projects", json=[])
    success(invoke(runner, "project", "list", "--archived"))
    assert parse_qs(urlsplit(http.calls[1].request.url).query)["archived"] == ["true"]


def test_all_pages_and_filters(runner, http):
    http.get(WS + "/projects", json=[{"id": "1"}, {"id": "2"}])
    http.get(WS + "/projects", json=[{"id": "3"}])
    data = success(
        invoke(runner, "project", "list", "--all", "--page-size", "2", "--name", "App")
    )
    assert [item["id"] for item in data] == ["1", "2", "3"]
    queries = [parse_qs(urlsplit(call.request.url).query) for call in http.calls]
    assert [q["page"] for q in queries] == [["1"], ["2"]]
    assert all(q["name"] == ["App"] for q in queries)


def test_all_pages_exact_multiple_ends_with_empty_page(runner, http):
    http.get(WS + "/tags", json=[{"id": "1"}])
    http.get(WS + "/tags", json=[])
    assert success(invoke(runner, "tag", "list", "--all", "--page-size", "1")) == [
        {"id": "1"}
    ]


def test_repeated_page_is_an_error_not_partial_success(runner, http):
    for _ in range(2):
        http.get(WS + "/projects", json=[{"id": "1"}])
    failure(
        invoke(runner, "project", "list", "--all", "--page-size", "1"),
        "repeated a page",
    )


def test_page_limit_is_explicit(runner, http):
    http.get(WS + "/projects", json=[{"id": "1"}])
    failure(
        invoke(
            runner, "project", "list", "--all", "--page-size", "1", "--max-pages", "1"
        ),
        "limit reached",
    )
    assert len(http.calls) == 1


def test_listing_rejects_wrong_response_shape(runner, http):
    http.get(WS + "/projects", json={"not": "a list"})
    failure(invoke(runner, "project", "list"), "non-list response")


@pytest.mark.parametrize(
    "resource,path_name",
    [
        ("client", "clients"),
        ("tag", "tags"),
        ("team", "user-groups"),
    ],
)
def test_named_resource_create(runner, http, resource, path_name):
    http.post(WS + "/" + path_name, json={"id": "new"}, status=201)
    assert success(invoke(runner, resource, "create", "研发 team")) == {"id": "new"}
    assert json.loads(http.calls[0].request.body) == {"name": "研发 team"}


def test_create_project(runner, http):
    http.post(WS + "/projects", json={"id": "p"}, status=201)
    success(
        invoke(
            runner,
            "project",
            "create",
            "Customer portal",
            "--client",
            "c",
            "--public",
            "--billable",
            "--color",
            "#AABBCC",
            "--note",
            "Phase 1",
        )
    )
    assert json.loads(http.calls[0].request.body) == {
        "name": "Customer portal",
        "clientId": "c",
        "isPublic": True,
        "billable": True,
        "color": "#AABBCC",
        "note": "Phase 1",
    }


def test_task_create_assignees(runner, http):
    http.post(WS + "/projects/p/tasks", json={"id": "t"}, status=201)
    success(
        invoke(
            runner,
            "task",
            "create",
            "p",
            "Implement API",
            "--assignee",
            "u1",
            "--assignee",
            "u2",
        )
    )
    assert json.loads(http.calls[0].request.body) == {
        "name": "Implement API",
        "assigneeIds": ["u1", "u2"],
    }


@pytest.mark.parametrize(
    "args,endpoint",
    [
        (["project", "update", "p"], "/projects/p"),
        (["client", "update", "c"], "/clients/c"),
        (["tag", "update", "t"], "/tags/t"),
        (["team", "update", "g"], "/user-groups/g"),
        (["task", "update", "p", "t"], "/projects/p/tasks/t"),
    ],
)
def test_resource_updates_forward_explicit_payload(
    runner, http, tmp_path, args, endpoint
):
    data = {"name": "Updated name", "archived": False}
    filename = tmp_path / "update.json"
    filename.write_text(json.dumps(data), encoding="utf-8")
    http.put(WS + endpoint, json={"id": "updated"})
    success(invoke(runner, *args, "--data", str(filename)))
    assert json.loads(http.calls[0].request.body) == data
    assert len(http.calls) == 1


@pytest.mark.parametrize(
    "args,endpoint,deleted",
    [
        (["project", "delete", "p"], "/projects/p", "p"),
        (["client", "delete", "c"], "/clients/c", "c"),
        (["tag", "delete", "t"], "/tags/t", "t"),
        (["team", "delete", "g"], "/user-groups/g", "g"),
        (["task", "delete", "p", "t"], "/projects/p/tasks/t", "t"),
        (["time", "delete", "e"], "/time-entries/e", "e"),
    ],
)
def test_delete_requires_yes_and_reports_id(runner, http, args, endpoint, deleted):
    failure(invoke(runner, *args), "--yes")
    assert not http.calls
    http.delete(WS + endpoint, status=204)
    assert success(invoke(runner, *args, "--yes")) == {"deleted": deleted}


def test_team_membership(runner, http):
    http.post(WS + "/user-groups/g/users", json={"userIds": ["u"]})
    success(invoke(runner, "team", "add-member", "g", "u"))
    assert json.loads(http.calls[0].request.body) == {"userId": "u"}
    failure(invoke(runner, "team", "remove-member", "g", "u"), "--yes")
    http.delete(WS + "/user-groups/g/users/u", status=204)
    assert success(invoke(runner, "team", "remove-member", "g", "u", "--yes")) == {
        "team_id": "g",
        "removed": "u",
    }


def test_manual_time_entry(runner, http, tmp_path):
    fields = [{"customFieldId": "f", "value": "Support"}]
    filename = tmp_path / "fields.json"
    filename.write_text(json.dumps(fields), encoding="utf-8")
    http.post(WS + "/time-entries", json={"id": "entry"}, status=201)
    success(
        invoke(
            runner,
            "time",
            "create",
            "--start",
            "2026-10-01T09:00:00+08:00",
            "--end",
            "2026-10-01T10:00:00+08:00",
            "--description",
            "Work",
            "--project",
            "p",
            "--task",
            "t",
            "--tag",
            "a",
            "--tag",
            "b",
            "--billable",
            "--custom-fields",
            str(filename),
        )
    )
    assert json.loads(http.calls[0].request.body) == {
        "start": "2026-10-01T01:00:00.000Z",
        "end": "2026-10-01T02:00:00.000Z",
        "description": "Work",
        "projectId": "p",
        "taskId": "t",
        "tagIds": ["a", "b"],
        "billable": True,
        "type": "REGULAR",
        "customFields": fields,
    }


def test_start_timer_defaults_to_now_and_has_no_end(runner, http, monkeypatch):
    monkeypatch.setattr(
        "cli_anything.clockify.commands.time.now", lambda: "2026-10-01T01:00:00.000Z"
    )
    http.post(WS + "/time-entries", json={"id": "running"}, status=201)
    success(
        invoke(runner, "time", "start", "--description", "Planning", "--non-billable")
    )
    assert json.loads(http.calls[0].request.body) == {
        "start": "2026-10-01T01:00:00.000Z",
        "description": "Planning",
        "billable": False,
        "type": "REGULAR",
    }


def test_stop_timer_uses_authenticated_user(runner, http):
    http.get(CORE_URL + "/user", json={"id": "me"})
    http.patch(WS + "/user/me/time-entries", json={"id": "stopped"})
    success(invoke(runner, "time", "stop", "--end", "2026-10-01T02:00:00Z"))
    assert json.loads(http.calls[1].request.body) == {"end": "2026-10-01T02:00:00.000Z"}


def test_stop_another_user_does_not_query_current_user(runner, http):
    http.patch(WS + "/user/other/time-entries", json={"id": "stopped"})
    success(invoke(runner, "time", "stop", "--user", "other"))
    assert len(http.calls) == 1
    assert json.loads(http.calls[0].request.body)["end"].endswith("Z")


def test_time_list_current_user_and_filters(runner, http):
    http.get(CORE_URL + "/user", json={"id": "me"})
    http.get(WS + "/user/me/time-entries", json=[])
    success(
        invoke(
            runner,
            "time",
            "list",
            "--in-progress",
            "--project",
            "p",
            "--start",
            "2026-10-01T00:00:00Z",
            "--description",
            "Review",
        )
    )
    query = parse_qs(urlsplit(http.calls[1].request.url).query)
    assert query == {
        "in-progress": ["true"],
        "project": ["p"],
        "start": ["2026-10-01T00:00:00.000Z"],
        "description": ["Review"],
        "page": ["1"],
        "page-size": ["50"],
    }


def test_time_update_is_full_put(runner, http, tmp_path):
    filename = tmp_path / "entry.json"
    filename.write_text(
        json.dumps(
            {
                "start": "2026-10-01T09:00:00+08:00",
                "end": None,
                "description": "Running",
                "tagIds": [],
                "billable": False,
            }
        ),
        encoding="utf-8",
    )
    http.put(WS + "/time-entries/e", json={"id": "e"})
    success(invoke(runner, "time", "update", "e", "--data", str(filename)))
    assert json.loads(http.calls[0].request.body) == {
        "start": "2026-10-01T01:00:00.000Z",
        "end": None,
        "description": "Running",
        "tagIds": [],
        "billable": False,
    }


@pytest.mark.parametrize("kind", ["summary", "detailed"])
def test_reports_have_correct_timezone_filters_and_host(runner, http, kind):
    payload = {"totals": [{"totalTime": 3600}], "timeentries": [{"id": "e"}]}
    http.post(REPORTS_URL + "/workspaces/ws/reports/" + kind, json=payload)
    args = [
        "report",
        kind,
        "--start",
        "2026-10-01T08:00:00+08:00",
        "--end",
        "2026-10-02T08:00:00+08:00",
        "--user",
        "u1",
        "--user",
        "u2",
        "--project",
        "p",
        "--client",
        "c",
        "--tag",
        "t",
        "--non-billable",
        "--description",
        "Planning",
    ]
    args += (
        ["--group", "USER", "--group", "PROJECT"]
        if kind == "summary"
        else ["--page", "3", "--page-size", "100"]
    )
    assert success(invoke(runner, *args)) == payload
    body = json.loads(http.calls[0].request.body)
    assert body["dateRangeStart"] == "2026-10-01T00:00:00.000"
    assert body["dateRangeEnd"] == "2026-10-02T00:00:00.000"
    assert body["timeZone"] == "UTC"
    assert body["dateRangeType"] == "ABSOLUTE"
    assert body["exportType"] == "JSON"
    assert body["users"] == {"ids": ["u1", "u2"], "contains": "CONTAINS"}
    for field, value in [("projects", "p"), ("clients", "c"), ("tags", "t")]:
        assert body[field] == {"ids": [value], "contains": "CONTAINS"}
    assert body["billable"] is False
    assert body["description"] == "Planning"
    if kind == "summary":
        assert body["summaryFilter"] == {"groups": ["USER", "PROJECT"]}
    else:
        assert body["detailedFilter"] == {"page": 3, "pageSize": 100}


@pytest.mark.parametrize(
    "args,message",
    [
        (
            [
                "time",
                "create",
                "--start",
                "2026-01-01",
                "--end",
                "2026-01-02T00:00:00Z",
            ],
            "timezone",
        ),
        (
            [
                "time",
                "create",
                "--start",
                "2026-01-02T00:00:00Z",
                "--end",
                "2026-01-01T00:00:00Z",
            ],
            "precede",
        ),
        (["time", "start", "--task", "t"], "requires --project"),
        (["project", "create", "X"], "2 to 250"),
        (["project", "create", "Demo", "--color", "red"], "RGB"),
        (["tag", "create", " "], "name"),
        (["project", "list", "--page", "0"], "range"),
        (["project", "list", "--page-size", "0"], "range"),
        (["project", "list", "--max-pages", "0"], "range"),
        (["report", "summary"], "Missing option"),
        (["not-a-command"], "No such command"),
    ],
)
def test_invalid_arguments_never_send_requests(runner, http, args, message):
    failure(invoke(runner, *args), message)
    assert not http.calls


@pytest.mark.parametrize(
    "content", ["{", "[]", '{"end": "2026-10-01T00:00:00Z"}', '{"start": 123}']
)
def test_invalid_time_update_file(runner, http, tmp_path, content):
    filename = tmp_path / "data.json"
    filename.write_text(content, encoding="utf-8")
    result = invoke(runner, "time", "update", "e", "--data", str(filename))
    assert result.exit_code != 0
    assert "error" in json.loads(result.stdout)
    assert not http.calls


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2026-01-02T00:30:00+02:00", "2026-01-01T22:30:00.000Z"),
        ("2026-01-01T23:30:00-02:00", "2026-01-02T01:30:00.000Z"),
        ("2026-01-01T09:00:00.125Z", "2026-01-01T09:00:00.125Z"),
    ],
)
def test_timestamp_normalizes_offsets(value, expected):
    assert timestamp(value) == expected


def test_missing_workspace_prevents_even_user_lookup(runner, http, monkeypatch):
    monkeypatch.delenv("CLOCKIFY_WORKSPACE_ID")
    failure(invoke(runner, "time", "stop"), "Select --workspace")
    assert not http.calls


def test_missing_key_has_json_error(runner, http, monkeypatch):
    monkeypatch.delenv("CLOCKIFY_API_KEY")
    failure(invoke(runner, "whoami"), "CLOCKIFY_API_KEY")
    assert not http.calls


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500])
def test_http_errors_are_structured_and_never_retried(runner, http, status):
    http.post(
        WS + "/time-entries",
        status=status,
        json={"message": "Rejected key " + KEY},
        headers={"Retry-After": "15"},
    )
    result = invoke(runner, "time", "start")
    error = failure(result, "Rejected key")
    assert error["status"] == status
    assert error["retry_after"] == "15"
    assert KEY not in result.output
    assert len(http.calls) == 1


@pytest.mark.parametrize("exception", [requests.Timeout, requests.ConnectionError])
def test_transport_errors_are_structured(runner, http, exception):
    http.post(WS + "/time-entries", body=exception(KEY))
    result = invoke(runner, "time", "start")
    assert result.exit_code == 1
    assert KEY not in result.output
    assert "error" in json.loads(result.stdout)
    assert len(http.calls) == 1


def test_invalid_json_success_is_not_hidden(runner, http):
    http.get(CORE_URL + "/user", body="<html>not JSON</html>", status=200)
    failure(invoke(runner, "whoami"), "invalid JSON")


def test_html_error_does_not_dump_response_body(runner, http):
    http.get(CORE_URL + "/user", body="<html>" + KEY + "</html>", status=502)
    result = invoke(runner, "whoami")
    failure(result, "HTTP 502")
    assert "<html>" not in result.output
    assert KEY not in result.output


def test_redirect_does_not_forward_credentials(runner, http):
    http.get(
        CORE_URL + "/user",
        status=302,
        headers={"Location": "https://unrelated.example/user"},
    )
    failure(invoke(runner, "whoami"), "HTTP 302")
    assert len(http.calls) == 1


def test_configured_hosts_and_timeout(runner, http, monkeypatch):
    monkeypatch.setenv("CLOCKIFY_API_URL", "https://region.example/api/v1/")
    http.get("https://region.example/api/v1/user", json={"id": "me"})
    assert success(invoke(runner, "--timeout", "4.5", "whoami")) == {"id": "me"}
    api = ClockifyAPI(KEY, timeout=4.5)
    try:
        with pytest.MonkeyPatch.context() as patch:
            call = {}

            def timeout_request(*args, **kwargs):
                call.update(kwargs)
                raise requests.Timeout()

            patch.setattr(api.http, "request", timeout_request)
            with pytest.raises(ClockifyError):
                api.request("POST", "time-entries", body={"start": "x"})
            assert call["timeout"] == 4.5
            assert call["allow_redirects"] is False
    finally:
        api.close()


@pytest.mark.parametrize(
    "url",
    [
        "http://api.clockify.me/api/v1",
        "https://user:pass@example.test/api",
        "file:///tmp/api",
        "https://example.test/api?key=secret",
    ],
)
def test_invalid_base_url_rejected(url):
    with pytest.raises(ClockifyError):
        ClockifyAPI(KEY, base_url=url)


def test_resource_ids_are_encoded():
    assert path("workspaces", "a/b?#") == "workspaces/a%2Fb%3F%23"
    for value in ["", ".", ".."]:
        with pytest.raises(ClockifyError):
            path("workspaces", value)


@pytest.mark.parametrize("value", ["nan", "inf"])
def test_timeout_must_be_finite(runner, http, value):
    failure(invoke(runner, "--timeout", value, "whoami"), "finite")
    assert not http.calls


def test_malformed_base_url_has_json_error(runner, http, monkeypatch):
    monkeypatch.setenv("CLOCKIFY_API_URL", "https://[invalid")
    failure(invoke(runner, "whoami"), "Invalid API URL")
    assert not http.calls


def test_repl_cannot_nest_via_global_options(runner, http):
    result = invoke(runner, input="--json repl\nworkspace current\nquit\n")
    assert result.exit_code == 0
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert "Already in the REPL" in lines[0]["error"]["message"]
    assert lines[1] == {"workspace_id": "ws"}
    assert not http.calls


def test_repl_preserves_workspace_json_and_user_cache(runner, http, monkeypatch):
    closed = []
    original_close = ClockifyAPI.close

    def close(api):
        closed.append(api)
        original_close(api)

    monkeypatch.setattr(ClockifyAPI, "close", close)
    http.get(CORE_URL + "/user", json={"id": "me"})
    http.get(CORE_URL + "/workspaces/other/user/me/time-entries", json=[])
    http.patch(
        CORE_URL + "/workspaces/other/user/me/time-entries", json={"id": "stopped"}
    )
    result = invoke(
        runner,
        input="workspace use other\nworkspace current\ntime list\ntime stop\nnot-real\nworkspace current\nquit\n",
    )
    assert result.exit_code == 0, result.output
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert lines[0] == lines[1] == lines[-1] == {"workspace_id": "other"}
    assert lines[2] == []
    assert lines[3] == {"id": "stopped"}
    assert "error" in lines[4]
    assert len(closed) == 1
    assert len(http.calls) == 3


def test_repl_handles_quotes_and_keeps_running(runner, http):
    http.post(WS + "/projects", json={"id": "p"}, status=201)
    result = invoke(
        runner,
        input='project create "App project"\nproject create "unterminated\nworkspace current\nquit\n',
    )
    assert result.exit_code == 0
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert lines[0] == {"id": "p"}
    assert "error" in lines[1]
    assert lines[2] == {"workspace_id": "ws"}
    assert json.loads(http.calls[0].request.body)["name"] == "App project"
