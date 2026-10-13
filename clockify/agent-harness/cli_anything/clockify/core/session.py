"""In-memory workspace selection shared by one-shot commands and the REPL."""

from dataclasses import dataclass

from cli_anything.clockify.core.api import ClockifyAPI, ClockifyError, path


@dataclass
class Session:
    api: ClockifyAPI
    workspace_id: str | None = None
    json_output: bool = False
    in_repl: bool = False

    def workspace_path(self, *parts: str) -> str:
        if not self.workspace_id:
            raise ClockifyError(
                "Select --workspace, set CLOCKIFY_WORKSPACE_ID, or use 'workspace use' in the REPL."
            )
        return path("workspaces", self.workspace_id, *parts)
