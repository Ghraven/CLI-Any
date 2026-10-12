"""Connection ownership, lifecycle, and real MCP stdio transport tests."""

import asyncio
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from types import SimpleNamespace

import anyio
import pytest
from click.testing import CliRunner

from cli_anything.browser import browser_cli
from cli_anything.browser.core.session import Session
from cli_anything.browser.utils import domshell_backend as backend
from cli_anything.browser.utils.mcp_connection import PersistentConnection


@pytest.fixture
def transport(monkeypatch):
    state = SimpleNamespace(
        starts=0,
        initializes=0,
        exits=0,
        calls=[],
        owners=[],
        threads=[],
        blocked=threading.Event(),
        fail_initialize=False,
        wait_initialize=False,
    )

    @asynccontextmanager
    async def stdio(params):
        state.starts += 1
        owner = asyncio.current_task()
        state.threads.append(threading.current_thread())
        try:
            async with anyio.create_task_group():
                yield None, None
        finally:
            state.owners.append(owner is asyncio.current_task())
            state.exits += 1

    class Client:
        async def __aenter__(self):
            self.owner = asyncio.current_task()
            return self

        async def __aexit__(self, *args):
            state.owners.append(self.owner is asyncio.current_task())

        async def initialize(self):
            state.initializes += 1
            if state.fail_initialize:
                raise ConnectionError("initialization failed")
            if state.wait_initialize:
                state.blocked.set()
                await asyncio.Event().wait()

        async def call_tool(self, name, arguments):
            state.calls.append(dict(arguments))
            command = arguments["command"]
            if command == "disconnect":
                raise ConnectionError("transport disconnected")
            if command == "wait":
                state.blocked.set()
                await asyncio.Event().wait()
            await asyncio.sleep(0)
            return SimpleNamespace(
                isError=command == "tool-error",
                content=[SimpleNamespace(text="ok\n[lane: 42]")],
            )

    monkeypatch.setattr(backend, "stdio_client", stdio)
    monkeypatch.setattr(backend, "ClientSession", lambda *args: Client())
    monkeypatch.setattr(backend, "_build_server_args", lambda: [])
    return state


def execute(session, command="ls"):
    return asyncio.run(backend._call_execute(command, session=session))


def test_ten_calls_use_one_connection_and_owner_task(transport):
    with Session() as session:
        for _ in range(10):
            execute(session)
        assert transport.starts == transport.initializes == 1
        assert transport.exits == 0
        assert session.domshell_lane_id == "42"
    assert [call["group_id"] for call in transport.calls] == ["new"] + ["42"] * 9
    assert transport.exits == 1
    assert transport.owners == [True, True]
    assert not transport.threads[0].is_alive()


def test_split_type_workflow_keeps_one_connection(transport):
    with Session() as session:
        backend.type_text("/main/input", "hello", session=session)
    assert transport.starts == 1
    assert [call["command"] for call in transport.calls] == [
        "cd %here%",
        "focus main/input",
        "type hello",
        "cd %here%",
    ]
    assert transport.owners == [True, True]


def test_sessions_have_separate_connections(transport):
    with Session() as first, Session() as second:
        execute(first)
        execute(second)
        first.close()
        execute(second)
    assert transport.starts == transport.exits == 2
    assert all(transport.owners)
    assert not any(thread.is_alive() for thread in transport.threads)


def test_concurrent_first_calls_create_one_connection_and_lane(transport):
    with Session() as session, ThreadPoolExecutor(max_workers=8) as callers:
        list(callers.map(lambda _: execute(session), range(20)))
    assert transport.starts == 1
    assert [call["group_id"] for call in transport.calls] == ["new"] + ["42"] * 19


def test_closed_session_cannot_reconnect(transport):
    session = Session()
    session.close()
    session.close()
    with pytest.raises(RuntimeError, match="session is closed"):
        execute(session)
    with pytest.raises(RuntimeError, match="session is closed"):
        with session:
            pass
    assert transport.starts == 0


def test_close_is_idempotent_after_use(transport):
    session = Session()
    execute(session)
    session.close()
    session.close()
    assert transport.exits == 1
    assert not transport.threads[0].is_alive()


def test_context_manager_closes_after_user_exception(transport):
    with pytest.raises(ValueError, match="user error"):
        with Session() as session:
            execute(session)
            raise ValueError("user error")
    assert transport.exits == 1
    assert not transport.threads[0].is_alive()


def test_failed_operation_is_not_replayed_and_next_command_reconnects(transport):
    with Session() as session:
        execute(session)
        with pytest.raises(RuntimeError, match="transport disconnected"):
            execute(session, "disconnect")
        assert transport.exits == 1
        execute(session, "cat")
    assert transport.starts == transport.exits == 2
    assert [call["command"] for call in transport.calls] == ["ls", "disconnect", "cat"]
    assert transport.calls[-1]["group_id"] == "42"
    assert all(transport.owners)


def test_failed_initialization_releases_resources(transport):
    with Session() as session:
        transport.fail_initialize = True
        with pytest.raises(RuntimeError, match="initialization failed"):
            execute(session)
        assert transport.exits == 1
        transport.fail_initialize = False
        execute(session)
    assert transport.starts == transport.exits == 2
    assert len(transport.calls) == 1


def test_tool_errors_do_not_discard_connection(transport):
    with Session() as session:
        result = execute(session, "tool-error")
        assert result.isError
        execute(session)
    assert transport.starts == transport.exits == 1


def test_request_timeout_closes_connection(transport, monkeypatch):
    monkeypatch.setattr(
        backend,
        "PersistentConnection",
        lambda *args: PersistentConnection(*args, timeout=0.05),
    )
    with Session() as session:
        with pytest.raises(RuntimeError, match="request timed out"):
            execute(session, "wait")
        assert transport.exits == 1
        execute(session)
    assert transport.starts == transport.exits == 2


def test_initialization_timeout_closes_connection(transport, monkeypatch):
    monkeypatch.setattr(
        backend,
        "PersistentConnection",
        lambda *args: PersistentConnection(*args, timeout=0.05),
    )
    transport.wait_initialize = True
    with Session() as session:
        with pytest.raises(RuntimeError, match="initialization timed out"):
            execute(session)
    assert transport.starts == transport.exits == 1
    assert not transport.threads[0].is_alive()


def test_close_during_initialization(transport):
    transport.wait_initialize = True
    with Session() as session, ThreadPoolExecutor(max_workers=1) as callers:
        result = callers.submit(execute, session)
        assert transport.blocked.wait(2)
        session.close()
        with pytest.raises(RuntimeError, match="closed"):
            result.result(timeout=2)
    assert transport.exits == 1
    assert not transport.threads[0].is_alive()


def test_cancellation_closes_connection(transport):
    async def cancel_call(session):
        task = asyncio.create_task(backend._call_execute("wait", session=session))
        assert await asyncio.to_thread(transport.blocked.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    with Session() as session:
        asyncio.run(cancel_call(session))
        assert transport.exits == 1
        execute(session)
    assert transport.starts == transport.exits == 2


def test_close_interrupts_active_and_queued_calls(transport):
    session = Session()
    with ThreadPoolExecutor(max_workers=2) as callers:
        active = callers.submit(execute, session, "wait")
        assert transport.blocked.wait(2)
        queued = callers.submit(execute, session, "ls")
        session.close()
        for result in (active, queued):
            with pytest.raises(RuntimeError):
                result.result(timeout=2)
    assert transport.exits == 1
    assert not transport.threads[0].is_alive()


@pytest.fixture
def cli_state(monkeypatch):
    monkeypatch.setattr(browser_cli, "_session", None)
    monkeypatch.setattr(browser_cli, "_repl_mode", False)
    monkeypatch.setattr(browser_cli, "_availability_cached", (True, "test backend"))
    monkeypatch.setattr(backend, "is_available", lambda: (True, "test backend"))
    yield
    browser_cli._close_session()


def test_one_shot_closes_connection(transport, cli_state):
    result = CliRunner().invoke(browser_cli.cli, ["--json", "fs", "ls"])
    assert result.exit_code == 0, result.output
    assert isinstance(json.loads(result.output), dict)
    assert transport.starts == transport.exits == 1
    assert browser_cli._session is None


def test_cli_failure_closes_connection(transport, cli_state):
    transport.fail_initialize = True
    result = CliRunner().invoke(browser_cli.cli, ["--json", "fs", "ls"])
    assert result.exit_code == 1
    assert "error" in json.loads(result.output)
    assert transport.exits == 1
    assert browser_cli._session is None


@pytest.mark.parametrize(
    "ending", ["quit", EOFError(), KeyboardInterrupt(), RuntimeError("prompt failed")]
)
def test_repl_reuses_connection_and_always_closes(
    transport, cli_state, monkeypatch, ending, tmp_path
):
    from cli_anything.browser.utils.repl_skin import ReplSkin

    inputs = iter(["fs ls", "fs ls", ending])

    def get_input(*args, **kwargs):
        line = next(inputs)
        if isinstance(line, BaseException):
            raise line
        return line

    monkeypatch.setattr(ReplSkin, "create_prompt_session", lambda *args: None)
    monkeypatch.setattr(ReplSkin, "get_input", get_input)
    initialize = ReplSkin.__init__
    monkeypatch.setattr(
        ReplSkin,
        "__init__",
        lambda self, *args, **kwargs: initialize(
            self,
            *args,
            history_file=str(tmp_path / "history"),
            **kwargs,
        ),
    )
    result = CliRunner().invoke(browser_cli.cli, [])
    assert result.exit_code == 0, result.output
    assert transport.starts == transport.exits == 1
    assert len(transport.calls) >= 2
    assert not transport.threads[0].is_alive()
    assert browser_cli._session is None
    assert not browser_cli._repl_mode


def test_real_stdio_reuses_process_and_preserves_server_state(tmp_path, monkeypatch):
    """Exercise the installed MCP SDK against a real JSON-RPC child process."""
    server = tmp_path / "server.py"
    log = tmp_path / "requests.jsonl"
    processes = []
    open_process = anyio.open_process

    async def record_process(*args, **kwargs):
        process = await open_process(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(anyio, "open_process", record_process)
    server.write_text(
        """
import json
import os
import sys
from pathlib import Path
log = Path(sys.argv[1])
cwd = "/"
for line in sys.stdin:
    request = json.loads(line)
    with log.open("a") as output:
        output.write(json.dumps({"pid": os.getpid(), **request}) + "\\n")
    if "id" not in request:
        continue
    if request["method"] == "initialize":
        result = {
            "protocolVersion": request["params"]["protocolVersion"],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "test-domshell", "version": "1.0"},
        }
    else:
        command = request["params"]["arguments"]["command"]
        if command.startswith("cd "):
            cwd = command[3:]
        result = {"content": [{"type": "text", "text": cwd + "\\n[lane: 42]"}]}
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(backend, "DEFAULT_SERVER_CMD", sys.executable)
    monkeypatch.setattr(
        backend, "_build_server_args", lambda: ["-u", str(server), str(log)]
    )
    with Session() as session:
        execute(session, "cd main")
        for _ in range(9):
            result = execute(session, "pwd")
            assert result.content[0].text == "main\n[lane: 42]"
        connection = session._connection
    requests = [json.loads(line) for line in log.read_text().splitlines()]
    assert len({request["pid"] for request in requests}) == 1
    assert sum(request["method"] == "initialize" for request in requests) == 1
    calls = [r["params"]["arguments"] for r in requests if r["method"] == "tools/call"]
    assert len(calls) == 10
    assert [call["group_id"] for call in calls] == ["new"] + ["42"] * 9
    assert connection.closed
    assert not connection._thread.is_alive()
    assert len(processes) == 1
    assert processes[0].returncode is not None
