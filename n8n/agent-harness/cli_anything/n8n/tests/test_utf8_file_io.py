"""File inputs must be decoded as UTF-8 regardless of the platform locale.

Runs the loader in a subprocess with UTF-8 mode off and an ASCII locale, which
mimics a Windows cp1252 default: ``open()`` without ``encoding=`` fails to
decode non-ASCII workflow files there.
"""

import json
import os
import subprocess
import sys

CODE = r"""
import sys
from cli_anything.n8n.n8n_cli import _load_json_arg
print(ascii(_load_json_arg("@" + sys.argv[1])["name"]))
"""


def test_load_json_arg_reads_utf8_under_ascii_locale(tmp_path):
    wf = tmp_path / "wf.json"
    wf.write_bytes(json.dumps({"name": "Café ワークフロー"}, ensure_ascii=False).encode("utf-8"))
    env = dict(os.environ, LC_ALL="C", LANG="C", PYTHONCOERCECLOCALE="0")
    env.pop("PYTHONUTF8", None)
    proc = subprocess.run(
        [sys.executable, "-X", "utf8=0", "-c", CODE, str(wf)],
        capture_output=True, env=env, cwd=os.getcwd(),
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert proc.stdout.decode("ascii").strip() == ascii("Café ワークフロー")
