# cli-anything-clockify

Time tracking, projects, teams and reports through the real
[Clockify REST APIs](https://docs.clockify.me/). Requires Python 3.10+ and a
Clockify account with API access. Workspace permissions and subscription
limits are enforced by Clockify.

## Install and configure

```bash
pip install "git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=clockify/agent-harness"
# Or, from this agent-harness directory:
pip install -e ".[dev]"

export CLOCKIFY_API_KEY="your-api-key"
cli-anything-clockify --json whoami
cli-anything-clockify --json workspace list
export CLOCKIFY_WORKSPACE_ID="workspace-id-from-the-response"
```

Generate an API key in Clockify's profile settings. The harness reads the key
from the environment; it has no command-line key option and writes no
credential or configuration files. HTTP connections close when the command
or REPL exits. Requests have a 30-second timeout, configurable with
`--timeout`; failed writes are not automatically retried.

For regional or custom Clockify deployments, set both complete base URLs:

| Variable | Default |
|---|---|
| `CLOCKIFY_API_URL` | `https://api.clockify.me/api/v1` |
| `CLOCKIFY_REPORTS_URL` | `https://reports.api.clockify.me/v1` |

Use the corresponding URLs from your deployment's Clockify documentation.
URLs require HTTPS; HTTP loopback addresses are supported for transport tests.
Redirects are reported as errors without forwarding the API key.

## Command groups

Global options precede the command: `cli-anything-clockify --json --workspace ID time list`.
Default output is formatted JSON; `--json` emits compact JSON. API failures
and subcommand validation failures produce an `error` object in JSON mode
and return a nonzero exit code. A 429 response includes `retry_after` when
the server provides it. Help and version output are text.

| Command | Operations |
|---|---|
| `whoami` | Authenticated user profile |
| `workspace` | `list`, `get`, `users`, `use`, `current` |
| `time` | `list`, `get`, `create`, `start`, `stop`, `update`, `delete` |
| `project` | `list`, `get`, `create`, `update`, `delete` |
| `client` / `tag` | `list`, `get`, `create`, `update`, `delete` |
| `task` | `list`, `get`, `create`, `update`, `delete`, scoped to a project ID |
| `team` | `list`, `create`, `update`, `delete`, `add-member`, `remove-member` |
| `report` | `summary`, `detailed` |
| `repl` | Interactive commands; also the default with no command |

Run any command with `--help` for its options. `team` operates on Clockify
user groups, not workspace invitations or account membership.

## Track time

```bash
cli-anything-clockify --json project list --all
cli-anything-clockify --json task list PROJECT_ID
cli-anything-clockify --json time start --project PROJECT_ID \
  --task TASK_ID --tag TAG_ID --description "Implement pagination" --billable
cli-anything-clockify --json time list --in-progress
cli-anything-clockify --json time stop

cli-anything-clockify --json time create \
  --start 2026-10-01T09:00:00+08:00 --end 2026-10-01T10:30:00+08:00 \
  --project PROJECT_ID --description "Review" --non-billable
cli-anything-clockify --json time get ENTRY_ID
cli-anything-clockify --json time delete ENTRY_ID --yes
```

All timestamps require a timezone and are normalized to UTC. `time start`
and `time stop` default to the current time. Time entry listing and stopping
default to the authenticated user; `--user ID` targets another user when
Clockify permits it. A task requires its project on creation.

For workspaces with required custom fields, pass `--custom-fields fields.json`
to `time create` or `time start`:

```json
[{"customFieldId": "FIELD_ID", "value": "Customer support"}]
```

## Update existing objects

`update` commands send a complete Clockify PUT request from `--data FILE`.
They do not merge fields with the existing object. Include every value you
want retained according to the endpoint's API schema; omitted fields may
reset. A time-entry update requires `start`:

```json
{
  "start": "2026-10-01T01:00:00Z",
  "end": "2026-10-01T02:30:00Z",
  "description": "Reviewed pagination",
  "projectId": "PROJECT_ID",
  "taskId": "TASK_ID",
  "tagIds": ["TAG_ID"],
  "billable": true,
  "type": "REGULAR"
}
```

```bash
cli-anything-clockify --json time update ENTRY_ID --data entry.json
cli-anything-clockify --json project update PROJECT_ID --data project.json
cli-anything-clockify --json team add-member TEAM_ID USER_ID
cli-anything-clockify --json team remove-member TEAM_ID USER_ID --yes
```

Deletion and membership removal require `--yes`. There is no local undo;
Clockify is the source of truth. On a write timeout, inspect the remote object
before deciding whether to repeat the command.

## Pagination and reports

Resource lists accept `--page`, `--page-size`, `--all` and `--max-pages`.
`--all` collects pages into one JSON array. It fails instead of silently
truncating when the page limit is reached or the server repeats a page.
`workspace list` returns the API's complete workspace list without pagination.

```bash
cli-anything-clockify --json time list --all \
  --start 2026-10-01T00:00:00Z --end 2026-10-08T00:00:00Z
cli-anything-clockify --json report summary \
  --start 2026-10-01T00:00:00+08:00 --end 2026-10-08T00:00:00+08:00 \
  --group USER --group PROJECT > summary.json
cli-anything-clockify --json report detailed \
  --start 2026-10-01T00:00:00Z --end 2026-10-08T00:00:00Z \
  --user USER_ID --project PROJECT_ID --page 1 --page-size 100 > detailed.json
```

Report filters support repeated `--user`, `--project`, `--client` and
`--tag`, plus description and billable filters. Input instants are converted
to UTC, and report requests explicitly set `timeZone: UTC` so profile timezone
settings do not shift the requested interval. Summary grouping defaults to
`PROJECT`. Detailed reports return one page with the server's totals; use
`--page` to request subsequent pages. The harness preserves report JSON
rather than recomputing totals or combining potentially overlapping totals.

## Interactive use

```text
$ cli-anything-clockify
workspace list
workspace use WORKSPACE_ID
project list
time start --description "Planning"
time stop
quit
```

Workspace selection persists for that REPL session. One-shot invocations use
`--workspace` or `CLOCKIFY_WORKSPACE_ID`; `workspace use` does not persist
across processes. The REPL reuses its HTTP session, handles quoted arguments,
and continues after command errors. For newline-delimited automation, pipe
commands to `cli-anything-clockify --json`; no banner or prompt is emitted.

## Tests

```bash
python -m pytest cli_anything/clockify/tests -m "not live" -q
# Read-only tests against a real account:
python -m pytest cli_anything/clockify/tests/test_full_e2e.py -m live -k read -q
# Full live lifecycle, only in a disposable workspace:
CLOCKIFY_LIVE_WRITES=1 python -m pytest cli_anything/clockify/tests/test_full_e2e.py -m live -q
```

Live tests require credentials and fail if selected without them. Offline
HTTP tests validate transport and request contracts, not service availability,
account permissions or plan-specific report behavior. The architecture and
test evidence are in `CLOCKIFY.md` and `tests/TEST.md` in the source tree.
