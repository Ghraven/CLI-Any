import json
import os
import tempfile

from cli_anything.mermaid.core import export as export_mod
from cli_anything.mermaid.core import project as project_mod
from cli_anything.mermaid.core.session import Session, default_state
from cli_anything.mermaid.utils import mermaid_backend


def test_default_state():
    state = default_state()
    assert "flowchart TD" in state["code"]
    assert json.loads(state["mermaid"])["theme"] == "default"


def test_save_open_roundtrip():
    session = Session()
    project_mod.new_project(session, sample="sequence")
    with tempfile.NamedTemporaryFile(suffix=".mermaid.json", delete=False) as fh:
        path = fh.name
    try:
        project_mod.save_project(session, path)
        other = Session()
        result = project_mod.open_project(other, path)
        assert result["line_count"] > 0
        assert "sequenceDiagram" in other.state["code"]
    finally:
        os.unlink(path)


def test_undo_redo():
    session = Session()
    session.new_project()
    original = session.state["code"]
    session.set_code("graph TD\n  A --> B\n")
    assert session.undo() is True
    assert session.state["code"] == original
    assert session.redo() is True
    assert "A --> B" in session.state["code"]


def test_backend_serialization_and_urls():
    serialized = mermaid_backend.serialize_state(default_state())
    assert serialized.startswith("pako:")
    assert mermaid_backend.build_render_url(serialized, "svg").startswith("https://")
    assert mermaid_backend.build_live_url(serialized, "view").startswith("https://")


def test_share_payload():
    session = Session()
    session.new_project()
    result = export_mod.share(session, mode="edit")
    assert result["mode"] == "edit"
    assert result["url"].startswith("https://mermaid.live/edit#")


def test_open_project_rejects_invalid_files():
    import pytest
    with tempfile.TemporaryDirectory() as tmp:
        bad_json = os.path.join(tmp, "bad.json")
        with open(bad_json, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        no_code = os.path.join(tmp, "nocode.json")
        with open(no_code, "w", encoding="utf-8") as fh:
            json.dump({"foo": 1}, fh)
        for path in (bad_json, no_code):
            session = Session()
            with pytest.raises(ValueError):
                session.open_project(path)
            assert not session.is_open


def test_render_http_error_is_runtime_error(monkeypatch):
    import io
    import urllib.error
    import pytest

    def boom(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO(b""))

    monkeypatch.setattr(mermaid_backend.urllib.request, "urlopen", boom)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out.svg")
        with pytest.raises(RuntimeError, match="HTTP 400"):
            mermaid_backend.render_to_file("pako:x", out, "svg")
        assert not os.path.exists(out)


def test_cli_reports_errors_without_traceback():
    from click.testing import CliRunner
    from cli_anything.mermaid.mermaid_cli import cli

    with tempfile.TemporaryDirectory() as tmp:
        bad = os.path.join(tmp, "bad.json")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("[]")
        result = CliRunner().invoke(cli, ["project", "open", bad])
        assert result.exit_code == 1
        assert "Error: Invalid Mermaid project file" in result.output
        assert not isinstance(result.exception, ValueError)


def test_nested_help_exits_zero():
    from click.testing import CliRunner
    from cli_anything.mermaid.mermaid_cli import cli

    for args in (["project", "--help"], ["diagram", "set", "--help"]):
        result = CliRunner().invoke(cli, args)
        assert result.exit_code == 0, result.output
        assert "Error" not in result.output


def test_autosave_failure_is_clean_error(monkeypatch):
    from click.testing import CliRunner
    from cli_anything.mermaid.core.session import Session
    from cli_anything.mermaid.mermaid_cli import cli

    def boom(self, *a, **k):
        raise PermissionError("read-only")

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "p.mermaid.json")
        session = Session()
        project_mod.new_project(session)
        project_mod.save_project(session, path)
        monkeypatch.setattr(Session, "save_project", boom)
        result = CliRunner().invoke(cli, ["--project", path, "diagram", "set", "--text", "graph TD; A-->B"])
        assert result.exit_code == 1
        assert "Error: read-only" in result.output
        assert not isinstance(result.exception, PermissionError)


def test_render_write_failure_is_runtime_error(monkeypatch, tmp_path):
    import io

    class FakeResp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(mermaid_backend.urllib.request, "urlopen", lambda *a, **k: FakeResp(b"<svg/>"))
    blocker = tmp_path / "file"
    blocker.write_text("x")
    with pytest.raises(RuntimeError, match="Could not write"):
        mermaid_backend.render_to_file("pako:x", str(blocker / "out.svg"), "svg")
