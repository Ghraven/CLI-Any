"""Local HTTP contract tests, not substitutes for live Clockify verification."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from .helpers import offline_env, run_cli


@pytest.fixture
def backend():
    calls = []
    entries = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def handle_request(self):
            body = None
            size = int(self.headers.get("Content-Length", "0"))
            if size:
                body = json.loads(self.rfile.read(size))
            calls.append(
                {
                    "method": self.command,
                    "url": self.path,
                    "body": body,
                    "key": self.headers.get("X-Api-Key"),
                }
            )
            endpoint = urlsplit(self.path).path
            status, result = 200, None
            if self.headers.get("X-Api-Key") != "transport-key":
                status, result = 401, {"message": "Missing API key"}
            elif endpoint == "/api/v1/user":
                result = {"id": "me"}
            elif endpoint == "/api/v1/workspaces":
                result = [{"id": "ws", "name": "Test workspace"}]
            elif (
                endpoint == "/api/v1/workspaces/ws/time-entries"
                and self.command == "POST"
            ):
                entry = {
                    **body,
                    "id": "entry-1",
                    "timeInterval": {"start": body["start"], "end": body.get("end")},
                }
                entries[entry["id"]] = entry
                status, result = 201, entry
            elif endpoint == "/api/v1/workspaces/ws/time-entries/entry-1":
                if self.command == "DELETE":
                    entries.pop("entry-1", None)
                    status = 204
                else:
                    result = entries["entry-1"]
            elif endpoint == "/api/v1/workspaces/ws/user/me/time-entries":
                if self.command == "PATCH":
                    entries["entry-1"]["timeInterval"]["end"] = body["end"]
                    result = entries["entry-1"]
                else:
                    result = list(entries.values())
            elif endpoint == "/api/v1/workspaces/ws/projects":
                query = parse_qs(urlsplit(self.path).query)
                result = (
                    [{"id": "p1"}, {"id": "p2"}]
                    if query["page"] == ["1"]
                    else [{"id": "p3"}]
                )
            elif endpoint.startswith("/reports/v1/workspaces/ws/reports/"):
                result = {
                    "totals": [{"totalTime": 3600}],
                    "timeentries": list(entries.values()),
                }
            else:
                status, result = 404, {"message": "Unknown test route"}
            encoded = json.dumps(result).encode("utf-8") if result is not None else b""
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        do_GET = handle_request
        do_POST = handle_request
        do_PATCH = handle_request
        do_DELETE = handle_request

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    env = {
        **offline_env(),
        "CLOCKIFY_API_KEY": "transport-key",
        "CLOCKIFY_WORKSPACE_ID": "ws",
        "CLOCKIFY_API_URL": origin + "/api/v1",
        "CLOCKIFY_REPORTS_URL": origin + "/reports/v1",
    }
    try:
        yield env, calls, entries
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def output(result):
    assert result.returncode == 0, (result.stdout, result.stderr)
    return json.loads(result.stdout)


def test_installed_cli_create_get_delete_over_http(backend):
    env, calls, entries = backend
    created = output(
        run_cli(
            "--json",
            "time",
            "create",
            "--start",
            "2026-10-01T09:00:00+08:00",
            "--end",
            "2026-10-01T10:00:00+08:00",
            "--description",
            "开发",
            "--billable",
            env=env,
        )
    )
    assert created["timeInterval"]["start"] == "2026-10-01T01:00:00.000Z"
    assert created["description"] == "开发"
    assert output(run_cli("--json", "time", "get", created["id"], env=env)) == created
    assert output(
        run_cli("--json", "time", "delete", created["id"], "--yes", env=env)
    ) == {"deleted": "entry-1"}
    assert not entries
    assert [c["method"] for c in calls] == ["POST", "GET", "DELETE"]
    assert all(c["key"] == "transport-key" for c in calls)


def test_installed_repl_timer_workflow(backend):
    env, calls, entries = backend
    env.pop("CLOCKIFY_WORKSPACE_ID")
    result = run_cli(
        "--json",
        env=env,
        input_text=(
            'workspace use ws\ntime start --start 2026-10-01T01:00:00Z --description "Design review"\n'
            "time list\ntime stop --end 2026-10-01T02:00:00Z\nquit\n"
        ),
    )
    assert result.returncode == 0, result.stderr
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert lines[0] == {"workspace_id": "ws"}
    assert lines[1]["timeInterval"]["end"] is None
    assert lines[2][0]["description"] == "Design review"
    assert lines[3]["timeInterval"]["end"] == "2026-10-01T02:00:00.000Z"
    assert sum(c["url"] == "/api/v1/user" for c in calls) == 1
    assert entries["entry-1"]["timeInterval"]["end"] == "2026-10-01T02:00:00.000Z"


def test_installed_cli_pagination_over_http(backend):
    env, calls, _ = backend
    result = output(
        run_cli("--json", "project", "list", "--all", "--page-size", "2", env=env)
    )
    assert [p["id"] for p in result] == ["p1", "p2", "p3"]
    assert len(calls) == 2


def test_installed_cli_report_separate_base_url(backend):
    env, calls, _ = backend
    result = output(
        run_cli(
            "--json",
            "report",
            "detailed",
            "--start",
            "2026-10-01T08:00:00+08:00",
            "--end",
            "2026-10-02T08:00:00+08:00",
            "--page",
            "2",
            env=env,
        )
    )
    assert result["totals"] == [{"totalTime": 3600}]
    assert calls[0]["url"] == "/reports/v1/workspaces/ws/reports/detailed"
    assert calls[0]["body"]["timeZone"] == "UTC"
    assert calls[0]["body"]["dateRangeStart"] == "2026-10-01T00:00:00.000"
    assert calls[0]["body"]["detailedFilter"]["page"] == 2


def test_installed_cli_json_http_error(backend):
    env, calls, _ = backend
    env["CLOCKIFY_API_KEY"] = "wrong-key"
    result = run_cli("--json", "whoami", env=env)
    assert result.returncode == 1
    assert json.loads(result.stdout)["error"]["status"] == 401
    assert len(calls) == 1
    assert "Traceback" not in result.stderr
