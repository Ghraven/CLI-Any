"""Streaming generation errors must reach callers and the CLI exit status."""

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from cli_anything.ollama.core.generate import stream_to_stdout


@pytest.mark.parametrize("prefix", [[], [{"response": "Partial", "done": False}]])
def test_stream_to_stdout_raises_on_error_chunk(prefix, capsys):
    chunks = iter(prefix + [{"error": "model runner failed"}])
    with pytest.raises(RuntimeError, match="model runner failed"):
        stream_to_stdout(chunks)
    assert capsys.readouterr().out == ("Partial" if prefix else "")


def test_generate_text_exits_unsuccessfully_on_http_200_stream_error():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path == "/api/generate"
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert data["stream"] is True
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            self.wfile.write(
                b'{"response":"Partial","done":false}\n'
                b'{"error":"model runner failed"}\n'
            )

        def log_message(self, format, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run([
                sys.executable, "-m", "cli_anything.ollama",
                "--host", f"http://127.0.0.1:{server.server_port}",
                "generate", "text", "--model", "test-model", "--prompt", "Hello",
            ], capture_output=True, text=True, timeout=10)
        finally:
            server.shutdown()
            thread.join(timeout=5)

    assert result.returncode == 1
    assert result.stdout == "Partial"
    assert "model runner failed" in result.stderr
