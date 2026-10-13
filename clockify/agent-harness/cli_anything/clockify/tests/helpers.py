"""Installed-command resolution shared by transport and service tests."""

import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path


def _resolve_cli(name: str = "cli-anything-clockify") -> list[str]:
    executable = Path(sysconfig.get_path("scripts")) / (
        name + (".exe" if os.name == "nt" else "")
    )
    if executable.is_file():
        return [str(executable)]
    found = shutil.which(name)
    if found:
        return [found]
    if os.environ.get("CLI_ANYTHING_FORCE_INSTALLED") == "1":
        raise RuntimeError(f"{name} is not installed in this environment")
    return [sys.executable, "-m", "cli_anything.clockify.clockify_cli"]


def run_cli(
    *args: str, env: dict[str, str] | None = None, input_text: str | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*_resolve_cli(), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        input=input_text,
        timeout=20,
    )


def offline_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("CLOCKIFY_")}
